
# SQL Inspector

Небольшой инструмент для статического анализа SQL-запросов под PostgreSQL.

## Возможности
- Проверка SQL-запросов на потенциальные проблемы (SELECT *, JOIN, функции в WHERE, GROUP BY и т.д.).
- Формирование JSON и HTML отчёта.
- Можно интегрировать в CI/CD.

## Установка
```bash
git clone <repo_url>
cd sql_project
pip install -r requirements.txt
```

## Запуск
```bash
python run_demo.py examples/query.sql
```

После выполнения появятся файлы:
- `report.json`
- `report.html`
