# SQL анализатор

Инструмент для стат. анализа SQL-скриптов на PostgreSQL.

## Возможности
- Проверка SQL-скриптов на проблемы по типу(SELECT *, JOIN, функции в WHERE, GROUP BY и т.д.).
- Формирование JSON и HTML отчётов.

## Установка
```bash
git clone https://github.com/AlexanderZhuzhgov/more_tech_VTB_Hackaton
cd sql_MORE_hack
pip install -r requirements.txt
```

## Запуск
```bash
python run_demo.py examples/query.sql
```

После выполнения появятся файлы:
- `report.json`
- `report.html`
