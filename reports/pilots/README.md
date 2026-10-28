# Пилоты Reports

Рабочие примеры проверяют выбранные решения до подключения общего стенда.
Данные синтетические. Звезда DWH, меры Cube и локальный Kafka реализованы; общий MinIO и репликация
не входят в этот исполняемый срез. Состав целевой системы — [150](../docs/150.component-diagram.md),
состояние работ — [план реализации](../docs/implementation-plan.md).

| Пилот | Артефакты | Что проверяется | Граница |
| --- | --- | --- | --- |
| P-01 ETL | `adapters.py`, `etl.py`, `db.py`, `demo.py` | Пять ресурсов Tracker → staging → PostgreSQL; повтор, пропавшая страница, rollback, checkpoint; версии справочников и суточный снимок | Реальные источники и расписание ожидают приёмки |
| P-02 Дашборд | `superset/`, `provision.py` | Superset R-01 → Cube SQL API; Keycloak; Gamma RLS по `sub` | Вход трёх пользователей, RLS, чужой фильтр и запрет SQL Lab подтверждены локально |
| P-03 Куб | `cube/cube.js`, `cube/model/TimeLogs.js` | M-01…M-20 с отдельным неутверждённым M-16, области доступа, drill-down и предагрегация | Нативный прогретый замер и контейнерный BI выполнены; холодный режим и общий стенд требуют проверки |

## 1. Проверки без Docker

Из корня репозитория, Python 3.12 и Node.js 22 или новее:

```bash
python3 -m venv reports/pilots/.venv
reports/pilots/.venv/bin/python -m pip install -r reports/pilots/requirements.txt
npm install --prefix reports/ci
PYTHON=reports/pilots/.venv/bin/python sh reports/ci/check.sh
```

SQLite в unit-тестах — изолированная проверка алгоритмов и API, не замена
PostgreSQL в архитектуре. Для настоящей временной PostgreSQL без Docker:

```bash
reports/pilots/.venv/bin/python -m pip install -r reports/pilots/requirements-test.txt
REPORTS_NATIVE_POSTGRES=1 PYTHON=reports/pilots/.venv/bin/python sh reports/ci/check.sh
```

`pgserver` запускает отдельный PostgreSQL на Unix-сокете в короткой временной
папке, без TCP. После проверки сервер останавливается и тестовая БД удаляется.
Для проверки своего изолированного PostgreSQL можно передать
`REPORTS_TEST_DATABASE_URL`; использовать только отдельную тестовую БД.

## 2. Проверка настоящего Cube без Docker

Для нативного прогона установить зависимости `cube/package.json` обычным
менеджером пакетов Node, включая официальные native-модули Cube. Используются
Node.js 22+ и зависимости `requirements-test.txt`.

```bash
npm install --prefix reports/pilots/cube
NODE_PATH="$PWD/reports/pilots/cube/node_modules" reports/pilots/.venv/bin/python reports/pilots/check_cube.py --record
```

Тест создаёт миллион синтетических строк во временном PostgreSQL, проверяет
реальный REST/SQL API, расчёт, предагрегацию в режиме rollup-only, свой scope и
детализацию. Затем делает 100 прогретых запросов при 20 клиентах. Тестовые ключи
и пароль SQL генерируются только в памяти и не являются доступами пользователя.
После проверки оба процесса Cube и PostgreSQL останавливаются.

[Нативный результат](artifacts/cube-benchmark.json): p95 0,0180 с; ARM64, 14 CPU,
PostgreSQL 16.2, Cube 1.6.75, Node 24.19.0. Очередь/кэш — memory, предагрегация —
в PostgreSQL. Замер включает SQL dataset с сортировкой Superset. Холодный режим
и Cubestore не проверены. Вход и RLS проверены отдельно в контейнерном BI ниже.

## 3. Контейнерный стенд

Требуются Docker с Compose v2 или новее и свободные loopback-порты 8180, 8088, 8081, 4000.
Образы: PostgreSQL 16.13, Keycloak 26.8.1, Superset 6.1.0 и Cube 1.6.75.
На ARM64 Mac установлен Docker CLI 29.9.2, Compose 5.6.1 и Colima 0.10.3
(Engine 29.5.2, профиль `reports`: 6 CPU, 10 GiB RAM, диск 40 GiB).
Установка: `brew install docker docker-compose docker-buildx colima`. Плагины
Compose/Buildx доступны в `~/.docker/cli-plugins`. Для этой копии используется
`DOCKER_CONTEXT=colima-reports`; контекст по умолчанию не менялся.

Локальный пилот использует очередь/кэш `memory` одного процесса Cube;
предагрегации остаются в PostgreSQL. У Cubestore 1.6.75 нет Linux ARM64-образа;
AMD64-контейнер под QEMU на этой машине не поднял HTTP-интерфейс. Cubestore
и многопроцессный режим необходимо проверить на общем стенде.
`CUBESQL_SQL_PUSH_DOWN=false` устраняет воспроизведённую ошибку aliases
при сортировке виртуального dataset поверх PostgreSQL-предагрегации.
Ограничение SQL API в 50 000 строк требует отдельной проверки больших
разрезов: локальный R-01 содержит шесть записей, нагрузочный срез — 300 групп.

Единственный источник секретов — `~/secrets.env`. `init_pilot_secrets.py` создаёт только недостающие
локальные демодоступы, сохраняет существующие значения и права 0600,
не выводит значения и не создаёт секретных файлов проекта. Не применять
его как средство выдачи production-доступов. `launch.py` читает только
следующие ключи; значений в репозитории, командных аргументах и новых `.env` нет:

- `REPORTS_DB_PASSWORD`, `REPORTS_CUBE_DB_PASSWORD`, `REPORTS_CUBE_SQL_PASSWORD`;
- `REPORTS_SUPERSET_SECRET_KEY` (не менее 32 символов), `REPORTS_SUPERSET_CLIENT_SECRET`;
- `REPORTS_KC_ADMIN_PASSWORD`, `REPORTS_DEMO_ADMIN_PASSWORD`, `REPORTS_DEMO_MEMBER_PASSWORD`.

```bash
reports/pilots/.venv/bin/python reports/ci/init_pilot_secrets.py
reports/pilots/.venv/bin/python reports/pilots/launch.py up --build -d --wait --wait-timeout 240
reports/pilots/.venv/bin/python reports/pilots/launch.py ps
```

Не запускайте `docker compose config` с загруженными секретами: команда
раскрывает подстановки. Файлы с секретами в проекте не создаются; провижининг держит
пароли и временный административный токен в памяти. `launch.py` перед выводом
маскирует известные секреты, их URL/JSON-представления и JWT. Общий том `/demo` содержит
только несекретные UUID пользователей для соответствия демоданных Keycloak.

В браузере открыть [Superset](http://localhost:8088), войти через Keycloak:
`member1`, `member2` или `admin`; пароль — соответствующее значение из
`~/secrets.env`. Дашборд — [R-01](http://localhost:8088/superset/dashboard/reports-r01/).
Значения эталона: `member1` — 3,75 часа, `member2` — 7,50, `admin` — 11,25.
Автоматическая проверка полного authorization-code flow:

```bash
reports/pilots/.venv/bin/python reports/pilots/check_roles.py --record
reports/pilots/.venv/bin/python reports/pilots/check_bi.py --record --benchmark
reports/pilots/.venv/bin/python reports/pilots/launch.py exec -T superset python /app/pythonpath/check_session.py
```

[Результат](artifacts/bi-verification.json): три входа, правильные суммы,
пустой результат при чужом фильтре, SQL Lab → 403; анонимный пользователь
и `noaccess` без роли Reports не получают сеанс. POST к изменяющему API
дашбордов без CSRF-токена возвращает 400; read-only chart-data в Superset
имеет штатное исключение CSRF. Скрипт не выводит пароли, cookies и токены.
Для локальных Secure cookies Keycloak он повторяет поведение браузера
только для `http://localhost:8180` и `:8088`.
Скриншоты реального R-01: [admin](artifacts/screenshots/admin-r01.png),
[member1](artifacts/screenshots/member1-r01.png),
[member2](artifacts/screenshots/member2-r01.png). При смене пользователя
завершать сеанс и в Superset, и в Keycloak. Сеанс Superset ограничен `exp`
проверенного access token и не продлевается активностью. После истечения
нужен новый OIDC-вход. `check_roles.py` временно отзывает роль только у
синтетического `member1` и восстанавливает её в `finally`; проверяет отказ
новому входу и последующее восстановление. Мгновенный back-channel logout
существующего сеанса пока не реализован. В этом же тесте временный
локальный клиент и новый ключ Keycloak проверяют обновление JWKS без
перезапуска API/Cube и вход Superset; исходный ключ и роль восстанавливаются,
временные ключ и клиент удаляются. Для Cube локальное окно повторного чтения неизвестного kid — 5 секунд;
тест допускает до 15 секунд на обновление JWKS. На общем Keycloak эта
процедура не выполнялась; интервалы и порядок ротации согласуются с Infra.

Тома `pg-data` и `kc-data` сохраняют метаданные и UUID пользователей.
Пересоздание контейнера Keycloak проверено с сохранением этих UUID;
удалять только его том при сохранённой БД Superset нельзя — появятся
новые `sub`, не соответствующие прежним учётным записям и RLS.
Состояние контейнеров — [протокол Docker](artifacts/docker-verification.json),
браузерные результаты — [протокол](artifacts/browser-verification.json).

В `app.subject_binding` провижининг записывает только известные соответствия
синтетического трекера и созданных пользователей Keycloak. Реальный ETL эту
таблицу не заполняет. Без подтверждённой записи API участника возвращает 403,
а Cube/Superset не сопоставляют неизвестные строки с `sub`; администратор
видит их в категории без подтверждённого пользователя. Параметры реального
Keycloak и соответствия сотрудников выдаются по Q-REP-11/16.

Cube REST доступен на `http://localhost:4000/cubejs-api/v1/load`, принимает
проверяемый JWT Keycloak с `aud=reports`. Пример тела параметра `query`:

```json
{"measures":["TimeLogs.hours"],"dimensions":["TimeLogs.projectId","TimeLogs.userId"],"timeDimensions":[{"dimension":"TimeLogs.loggedDate","granularity":"month"}]}
```

Участнику сервер добавляет фильтр собственного `sub`. Общая SQL-учётная запись
BI не публикуется наружу; ограничения конечного пользователя в этом соединении
обеспечиваются Superset RLS. Нельзя выдавать участникам доступ к SQL Lab или
сырой базе. Роль PostgreSQL `reports_cube` читает только
`dwh.report_time_log`; исходные записи, история HR и `app.subject_binding`
ей напрямую недоступны. Пилотный API `GET /pilot/reports/time-logs?group=project` использует
тот же проверенный `sub`; варианты `group`: `project`, `employee`, `month`, `record`.
Параметры `startDate`/`endDate` передаются парой (YYYY-MM-DD); границы включены.
`limit` — 1…1000, `offset` — от 0; ответ содержит `totalGroups` и `hasMore`.
Область пользователя применяется до периода, группировки и пагинации.
Этот ограниченный read-only API не объявляет реализацию всего `api/openapi/v1`.

Остановка сохраняет данные томов:

```bash
reports/pilots/.venv/bin/python reports/pilots/launch.py down
```

## 4. Локальная надёжность и повторяемость

`etl-scheduler` выполняет полную загрузку пяти ресурсов Tracker каждые
60 секунд. Запуски последовательны; пропущенные такты не догоняются пачкой.
PostgreSQL дополнительно блокирует конкурирующую загрузку того же источника.
Сбой сохраняет checkpoint и данные, а API показывает STALE. `/health` и
`/livez` проверяют процесс; `/readyz` требует свежую успешную загрузку и БД.
Планировщик сообщает health по последнему циклу без секретов; после сбоя он unhealthy.

Для отдельного задания есть `etl.py --every 3600` и ограничитель `--runs N`;
`run_etl.py` передаёт эти аргументы и читает секреты из единственного хранилища.
Расписание реальных источников необходимо согласовать; демо не доказывает
целевой сквозной лаг реальных источников. Локальные `ops`, Kafka и сверка реализованы — [описание](../docs/star-events-implementation.md).

Версии справочников хранятся в `dwh.dimension_version`: изменённая запись
закрывает текущий интервал и открывает новый; неизменённая не дублируется.
`is_deleted` сохраняется как явный tombstone. Отсутствие строки не означает
удаление. Первая успешная полная партия за UTC-день атомарно создаёт
`etl.snapshot_batch` и `dwh.source_snapshot`; позже в этот снимок ничего
не дописывается. Снимок не выдаётся за снимок строго в 02:00 или восстановление
истории источника до первого запуска.

Нативные PostgreSQL-тесты выполняют настоящий `pg_dump`/`pg_restore` между
двумя отдельными временными БД. Проверены часы, версии, снимки, checkpoint,
область member и повторная загрузка; испорченный архив отклоняется.
[Протокол](artifacts/restore-verification.json). Это проверка алгоритма
восстановления Reports, а не RPO/RTO общего стенда или копирования Keycloak.

Для проверки пустых томов:

```bash
reports/pilots/.venv/bin/python reports/pilots/check_clean.py
```

Команда на время освобождает localhost-порты, сохраняет исходные тома,
создаёт уникальный `reports-check-*` проект, проверяет реальные OIDC/RLS,
удаляет только созданные тестовые тома и в `finally` восстанавливает исходный
стенд. Не запускать параллельно с другой работой со стендом. Результат —
[проверка чистого запуска](artifacts/clean-stack-verification.json), безопасный
журнал — `artifacts/clean-stack.log`.

Для локального профиля 6 CPU / 10 GiB Superset запускается как 4 процесса
Gunicorn с 5 потоками каждый. Два синхронных процесса давали очередь
при 20 сеансах; параметры общего стенда и его пределы требуют приёмки Infra.

`check_bi.py --benchmark` отдельно измеряет 100 запросов chart-data API через
20 изолированных сеансов двух участников на шести демозаписях с прогретыми
Cube и кэшем графиков Superset (метаданные PostgreSQL, TTL 60 секунд).
Проверяются cache hits и область каждого ответа. Основные проверки
корректности отдельно выполняются с force reload. Это включает
Superset RLS, но не отрисовку браузера и не миллион строк нативного теста.
[Результат BI](artifacts/bi-benchmark.json): p95 0,18 с, 100 cache hits из
100 запросов в локальном прогоне 2026-10-24. Отдельно сохранён
[базовый принудительный режим](artifacts/bi-force-refresh-baseline.json):
p95 3,9656 с при 20 клиентах, до включения кэша графиков. Этот результат
не выдаётся за выполнение порога 3 с. Холодная первая загрузка Cube
измеряется в `cube-benchmark.json`; полный холодный BI остаётся непроверенным.

Соединение Superset использует пакет `superset/cube_driver` и URI с протоколом
`reports_cube+psycopg2`. Пакет регистрирует диалект SQLAlchemy и EngineSpec
через штатные entry points: версия берётся из libpq handshake, схема Cube
фиксирована как `public`. Это устраняет служебные SQL-запросы определения
схемы при каждом обращении к кэшу. Запросы данных, пароль SQL API и RLS
сохраняются; обычные подключения PostgreSQL используют прежний драйвер.
Выбор адаптера и срок сеанса проверяются внутри настоящего образа Superset
командой `check_session.py`.

При проверках на Colima наблюдалась ошибка Cube SQL `SystemTimeError`
при движении часов VM назад, с разрывом SQL-соединения. Адаптер сокращает
служебные запросы, но не исправляет обработку часов внутри Cube. Успешный
текущий прогон не доказывает устойчивость к повторному скачку времени:
для эксплуатационной приёмки нужны стабильные часы VM и проверка этого
сценария с Infra либо исправление в Cube.

## 5. Реальные источники

После выдачи отдельной тестовой БД и минимального токена потребителя добавить
их в `~/secrets.env` как `REPORTS_DATABASE_URL` и `REPORTS_SOURCE_TOKEN`.
Не использовать собственную БД соседней команды. Например, только чтение
Reference Manager и загрузка в собственный DWH:

```bash
reports/pilots/.venv/bin/python reports/pilots/run_etl.py --source reference --url https://reference-manager.example
```

Аналогично `--source qa`, `--source tracker`; для Planning — `--source planning`
и `--portfolio-id`. POST к Planning создаёт только партию чтения; пользовательские
планы, сотрудники, задачи и тесты не изменяются. HTTP разрешается отдельным
`--allow-http` только на изолированном локальном стенде. Перенаправления запрещены,
чтобы Bearer не ушёл другому серверу. Ошибки не журналируют токены и тела источников.

Адаптеры сохраняют исходные `is_deleted`, `quality`, `missingInputs` и отсутствие
денег. Они не домысливают удаление по отсутствующей строке. Полные преобразования
QA/Planning/HR в типизированные бизнес-факты реализованы в `star.py`. Измерения
звезды имеют SCD2, факты — внешние ключи и неизвестный ключ -1. Это не заменяет
догрузку истории до первого запуска и согласование межсистемных соответствий. Пустой checkpoint не означает
приёмку отчётов на реальных источниках. Нет общего snapshot Task Tracker: сверка totals/ID
обнаруживает часть расхождений, но не гарантирует согласованный межресурсный срез.

## 6. Критерии и справочные материалы

Расширенный эталон — `acceptance_data.py`, seed `reports-acceptance-v1`:
3 проекта, 2 итерации, 40 задач, 300 записей трудозатрат, 2 прогона,
15 дефектов с переоткрытием. Это отдельный E2E-набор; компактный дашборд
Compose сохраняет прежние 6 записей и суммы 3,75/7,50/11,25 ч.
`check_postgres.py --record` автоматически проверяет все четыре HTTP-адаптера,
отдельный PostgreSQL и HTTP API с RSA/JWKS. Итог эталона — 562,50 ч;
ожидаемые суммы и границы покрытия — [T-01…T-35](../docs/test-evidence.md).
Результат — [протокол E2E](artifacts/acceptance-verification.json).

Дополнительно проверяются cookie-only отказ API, неизвестные/повторные
параметры, read-only методы, отсутствие CORS и строгий массив строковых ролей.
Superset отвергает изменяющие запросы с чужим Origin даже с действующим
CSRF-токеном; allowlist пилота — `http://localhost:8088`. Для общего стенда
нужна отдельная конфигурация допустимого origin. HTML sanitation и Markdown
escaping включены явно; проверка настроек не считается браузерным XSS-тестом.
Сканер секретов запускается в CI по исходникам и артефактам без вывода значений.

- P-01: эталонный результат, идемпотентность, отказ неполной партии, атомарность.
- P-02: вход трёх пользователей, изоляция двух участников, запрет обхода RLS.
- P-03: расчёт и детализация, проверка предагрегации, p95 ≤ 3 с на миллионе
  трудозатрат при 20 клиентах; фиксируются версия, холодный/прогретый режим,
  аппаратные ресурсы, число запросов и распределение задержек.
- CI: [локальная команда](../ci/check.sh), [шаблон workflow](../ci/workflow.example.yaml).
  Шаблон внутри `reports/` GitHub автоматически не запускает; регистрацию в
  `.github/workflows` следует согласовать отдельно.

Команды полной локальной проверки и состав безопасных артефактов —
[инструкция CI](../ci/README.md).

Подробный статус замечаний — [реестр](../docs/review-status.md).

Конфигурация основана на [настройках Superset](https://superset.apache.org/docs/configuration/configuring-superset/),
[безопасности Superset](https://superset.apache.org/docs/security/),
[контексте Cube](https://docs.cube.dev/docs/data-modeling/access-control/context)
и [настройках Cube](https://docs.cube.dev/reference/configuration/config).
