# SQL анализатор

Инструмент для стат. анализа SQL-скриптов на PostgreSQL.
Тестовая БД взята отсюда - https://postgrespro.ru/education/demodb

## Возможности
- Проверка SQL-скриптов на проблемы по типу(SELECT *, JOIN, функции в WHERE, GROUP BY и т.д.).
- Формирование JSON и HTML отчётов.
- Ну и расчёт костов ДО и после оптимизации

## Установка
```bash
git clone https://github.com/AlexanderZhuzhgov/more_tech_VTB_Hackaton
cd <sql_MORE_hack>  --Жюри выберет свою папку
```

## Запуск
```bash
python analyzer.py --sql demo.sql --out-json demo_report.json --out-html demo_report.html
```

После выполнения появятся файлы:
- `demo_report.json`
- `demo_report.html`
