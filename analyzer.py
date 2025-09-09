#!/usr/bin/env python3
"""SQL Анализатор для хакатона ВТБ More_Tech
Жужгов Александр
Жужгова Ольга
Usage:
  python analyzer.py --sql demo.sql --out-json reports.json --out-html reports.html
"""

import re, json, argparse, datetime, math, os

def normalize_sql(sql: str) -> str:
    sql = re.sub(r"--.*?$", "", sql, flags=re.M)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    sql = " ".join(sql.split())
    return sql.strip()

def detect_patterns(sql: str):
    s = sql.lower()
    patterns = []
    if "select *" in s:
        patterns.append({"code":"SELECT_STAR","desc":"Используется SELECT * — возврат всех колонок может привести к избыточному объёму данных и кривой сортировке"})
    if re.search(r"\border\s+by\b", s):
        patterns.append({"code":"ORDER_BY","desc":"ORDER BY — возможна затратная сортировка/генерятся spills."})
    if re.search(r"\boffset\s+\d+", s):
        off = int(re.search(r"\boffset\s+(\d+)", s).group(1))
        patterns.append({"code":"OFFSET","desc":f"OFFSET {off} — пагинация с большим смещением сканирует пропущенные строки."})
    joins = len(re.findall(r"\bjoin\b", s))
    if joins:
        patterns.append({"code":"JOINS","desc":f"{joins} JOIN(s) — соединения могут быть проблематичны без индексов по join-ключам."})
    if re.search(r"\blike\s*'%", s):
        patterns.append({"code":"LIKE_LEADING_WILDCARD","desc":"LIKE с ведущим % — индексы не используются."})
    if re.search(r"\bgroup\s+by\b", s) or "distinct" in s:
        patterns.append({"code":"AGGREGATION","desc":"GROUP BY/DISTINCT — требует сортировки или хеширования."})
    if re.search(r"\b(date_trunc|lower|upper|substring|substr|cast|coalesce)\s*\(", s):
        patterns.append({"code":"FUNC_ON_COLUMN","desc":"Функции над колонками в WHERE/JOIN мешают использованию индексов."})
    in_lists = re.findall(r"\bin\s*\(([^)]+)\)", s)
    for lst in in_lists:
        n = len([x for x in re.split(r"\s*,\s*", lst.strip()) if x])
        if n > 10:
            patterns.append({"code":"LARGE_IN_LIST","desc":f"IN-list из {n} элементов — лучше использовать временную таблицу/JOIN."})
    return patterns

def demo_cost(sql: str):
    s = normalize_sql(sql).lower()
    base = 0
    notes = []
    m = re.search(r"\blimit\s+(\d+)", s)
    est_rows = int(m.group(1)) if m else 100000
    base += est_rows * 20
    notes.append(f"Row factor: {est_rows} * 20 => {est_rows*20}")
    if "select *" in s:
        base += 10000; notes.append("SELECT * penalty +10000")
    joins = len(re.findall(r"\bjoin\b", s))
    if joins:
        base += joins * 50000; notes.append(f"{joins} JOIN(s) penalty +{joins*50000}")
    if re.search(r"\border\s+by\b", s):
        base += 200000; notes.append("ORDER BY penalty +200000")
    offm = re.search(r"\boffset\s+(\d+)", s)
    if offm:
        offv = int(offm.group(1))
        if offv > 10000:
            base += 500000; notes.append(f"Large OFFSET {offv} penalty +500000")
        else:
            base += 150000; notes.append(f"OFFSET {offv} penalty +150000")
    if re.search(r"\blike\s*'%", s):
        base += 120000; notes.append("Leading wildcard LIKE +120000")
    if re.search(r"\b(date_trunc|lower|upper|substring|substr|cast|coalesce)\s*\(", s):
        base += 90000; notes.append("Function on column +90000")
    if re.search(r"\bgroup\s+by\b", s) or "distinct" in s:
        base += 180000; notes.append("GROUP BY/DISTINCT +180000")
    risk = "Low"
    if base > 600000: risk = "High"
    elif base > 250000: risk = "Medium"
    row_width = 120
    est_pages = max(1, math.ceil(est_rows * (row_width/8192.0)))
    est_mem = min(2_000_000_000, est_rows * (row_width + 24))
    return {
        "score": int(base),
        "notes": notes,
        "est_rows": est_rows,
        "est_row_width": row_width,
        "est_io_pages": est_pages,
        "est_mem_bytes": est_mem,
        "risk": risk
    }

def recommend(sql: str):
    s = normalize_sql(sql).lower()
    recs = []
    if "select *" in s:
        recs.append({"priority":"Medium","category":"SQL","title":"Указать явный список колонок вместо SELECT *","explain":"Сокращает передачу ненужных данных, уменьшает ширину строк и нагрузку на сортировку/агрегацию.","estimated_impact":"x1.1–x1.3"})
    if re.search(r"\border\s+by\b", s):
        m = re.search(r"order\s+by\s+([a-z0-9_.]+)", s)
        col = m.group(1) if m else "колонку"
        recs.append({"priority":"High","category":"Index","title":f"Композитный индекс под ORDER BY ({col}) и фильтры","explain":"Устраняет сортировку и снижает вероятность spill на диск.","estimated_impact":"x2–x10"})
    off = re.search(r"\boffset\s+(\d+)", s)
    if off and int(off.group(1)) > 1000:
        recs.append({"priority":"High","category":"SQL","title":"Заменить OFFSET на keyset-пагинацию","explain":"Keyset (seek) пагинация позволяет избегать сканирования пропущенных строк.","estimated_impact":"x5–x100 (на глубоких страницах)"})
    joins = len(re.findall(r"\bjoin\b", s))
    if joins:
        recs.append({"priority":"High","category":"Index","title":"Индексы по ключам соединений","explain":"Индексация join-ключей значительно ускоряет соединения, убирает Hash/SeqScan.","estimated_impact":"x2–x8"})
    if re.search(r"\blike\s*'%", s):
        recs.append({"priority":"Medium","category":"SQL","title":"Избегать ведущего '%' в LIKE — использовать текстовый поиск или trigram","explain":"Ведущий wildcard не использует B-tree; fulltext/trigram/fts более эффективны.","estimated_impact":"x3–x50"})
    if re.search(r"\b(date_trunc|lower|upper|substring|substr|cast|coalesce)\s*\(", s):
        recs.append({"priority":"Medium","category":"SQL","title":"Не применять функции к индексируемым колонкам в WHERE/JOIN","explain":"Функции мешают использованию индексов, лучше хранить пред-вычисленные значения или использовать expression index.","estimated_impact":"x1.5–x5"})
    if re.search(r"\border\s+by\b", s) or re.search(r"\bgroup\s+by\b", s):
        recs.append({"priority":"Medium","category":"Config","title":"Повысить work_mem для сессии/запроса","explain":"Снижение вероятности temp spill, особенно для больших сортировок/агрегаций.","estimated_impact":"x1.2–x3"})
    return recs

def simulate_whatif(before_score, recs):
    cost = float(before_score)
    for r in recs:
        if r["priority"] == "High": cost *= 0.45
        elif r["priority"] == "Medium": cost *= 0.85
        else: cost *= 0.95
    return int(max(1, cost))

def to_human(n):
    units = ['B','KB','MB','GB','TB']
    v = float(n); i = 0
    while v >= 1024 and i < len(units)-1:
        v /= 1024.0; i += 1
    return f"{v:.1f} {units[i]}"

def build_reports(sql_text):
    patterns = detect_patterns(sql_text)
    cost = demo_cost(sql_text)
    recs = recommend(sql_text)
    after = simulate_whatif(cost["score"], recs)
    report = {
        "generated_at": datetime.datetime.utcnow().isoformat() + 'Z',
        "sql": sql_text,
        "patterns": patterns,
        "analysis": cost,
        "recommendations": recs,
        "what_if": {
            "cost_before": cost["score"],
            "cost_after": after,
            "estimated_speedup": round(max(1.0, cost["score"] / max(1, after)), 2)
        }
    }
    return report
#ОЛЯ отредачь вот этот кусок
def render_html(report):
    def row(k,v): return f"<tr><th>{k}</th><td>{v}</td></tr>"
    html = """<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>SQL-анализатор для хакатона от ВТБ More_Tech</title>
<style>body{font-family:Arial,Helvetica,sans-serif;margin:20px}pre{background:#f6f8fa;padding:10px;border-radius:6px}table{border-collapse:collapse;width:100%}th,td{padding:8px;border:1px solid #eee}</style></head><body>"""
    html += f"<h1>SQL-анализатор для хакатона от ВТБ More_Tech</h1><div><strong>Сгенерировано:</strong> {report['generated_at']}</div>"
    html += f"<h2>Запрос</h2><pre>{report['sql'].strip()}</pre>"
    html += "<h2>Найденные паттерны</h2><ul>" + ("".join(f"<li><strong>{p['code']}</strong>: {p['desc']}</li>" for p in report['patterns']) or '<li>Нет</li>') + "</ul>"
    html += "<h2>Анализ стоимости</h2><table>"
    html += row('Score (arb.)', f"{report['analysis']['score']:,}") + row('Risk', report['analysis']['risk'])
    html += row('Estimated rows', f"{report['analysis']['est_rows']:,}") + row('Estimated IO pages', f"{report['analysis']['est_io_pages']:,}")
    html += row('Estimated memory', to_human(report['analysis']['est_mem_bytes'])) + "</table>"
    html += "<h3>Notes</h3><ul>" + ("".join(f"<li>{n}</li>" for n in report['analysis']['notes']) or '<li>Нет</li>') + "</ul>"
    html += "<h2>Рекомендации</h2><ol>" + ("".join(f"<li><strong>{r['priority']}</strong> [{r['category']}]: <strong>{r['title']}</strong> — {r['explain']} — <em>{r['estimated_impact']}</em></li>" for r in report['recommendations']) or '<li>Нет</li>') + "</ol>"
    html += f"<h2>What-if: До/После</h2><p>Cost before: {report['what_if']['cost_before']:,} — Cost after: {report['what_if']['cost_after']:,} (estimated speedup ×{report['what_if']['estimated_speedup']})</p>"
    html += "</body></html>"
    return html

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", required=True, help="SQL text or path to SQL file")
    ap.add_argument("--out-json", default="reports.json", help="Output JSON")
    ap.add_argument("--out-html", default="reports.html", help="Output HTML")
    args = ap.parse_args()

    sql_text = args.sql
    if os.path.exists(sql_text):
        with open(sql_text, 'r', encoding='utf-8') as f:
            sql_text = f.read()

    report = build_reports(sql_text)
    with open(args.out_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(args.out_html, 'w', encoding='utf-8') as f:
        f.write(render_html(report))
    print(f"Wrote {args.out_json} and {args.out_html}")

if __name__ == '__main__':
    main()
