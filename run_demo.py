
import sys
import json
from jinja2 import Template
from analyzer.core import SqlInspector

def main(sql_file: str):
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_text = f.read()

    inspector = SqlInspector(sql_text)
    result = inspector.run()

    # Save JSON
    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Save HTML
    template = Template("""
    <html>
    <head><title>SQL Report</title></head>
    <body>
    <h1>SQL Analysis Report</h1>
    <h2>Issues</h2>
    <ul>
    {% for issue in issues %}
      <li><b>{{ issue.level }}</b>: {{ issue.message }}</li>
    {% endfor %}
    </ul>
    </body>
    </html>
    """)
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(template.render(issues=result["issues"]))

    print("Готово. Смотрите report.json и report.html")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python run_demo.py <sql_file>")
        sys.exit(1)
    main(sys.argv[1])
