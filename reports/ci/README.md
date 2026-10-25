# Локальная CI Reports

Все исполняемые проверки находятся внутри `reports/`. Из корня репозитория:

```bash
python3 -m venv reports/pilots/.venv
reports/pilots/.venv/bin/python -m pip install -r reports/pilots/requirements-test.txt
npm install --prefix reports/ci
reports/pilots/.venv/bin/python reports/ci/record_checks.py --native-postgres
```

Запуск включает контракты/ссылки, эталонные E2E на отдельном PostgreSQL,
unit-тесты, проверки Cube scope, синтаксис Mermaid, diff и сканер секретов.
Нужны Python 3.12, Node 22+, возможность открыть loopback-сокеты и запустить
временный PostgreSQL. Тестовые БД создаются отдельно и удаляются в `finally`.

Для настоящего локального BI дополнительно нужен Docker Compose и именованные
значения в единственном хранилище `~/secrets.env`. На пустой машине demo-only
значения добавляет `init_pilot_secrets.py`, сохраняя существующие ключи.

```bash
reports/pilots/.venv/bin/python reports/pilots/launch.py up --build -d --wait --wait-timeout 240
reports/pilots/.venv/bin/python reports/ci/record_checks.py --native-postgres --bi
```

Ротация/отзыв выполняются только в локальном realm `reports-pilot`; синтетические
роль и ключ восстанавливаются. Протоколы JSON и безопасные логи сохраняются в
`pilots/artifacts`. Сканер не выводит значения: только пути и категории ошибок.
Он проверяет известные ключи из `~/secrets.env`, JWT и приватные ключи; это не
гарантия обнаружения любого неизвестного формата секрета.

[Шаблон GitHub Actions](workflow.example.yaml) запускает отдельные unit/E2E и
BI jobs и публикует только перечисленные JSON-протоколы. GitHub не обнаруживает
workflow в `reports/ci`; регистрация требует изменения `.github/workflows`
за пределами текущего разрешённого объёма. Удалённый запуск не заявляется.
