# Разработка и запуск

## Поставка и границы

FastAPI + PostgreSQL, контрактные snapshots, idempotency/ETag, CRUD проектов,
версии/согласование/активация, прогноз, immutable ETL batch, release-context и
вложения. API соответствует [130](docs/130.api-contracts.md); дополнительные
ресурсные/UI-маршруты описываются в runtime.openapi.json. 12 экранов сохраняют
навигацию и оформление [прототипа](ui/prototype/index.html), но обращаются к серверу.
Фактическая схема БД — migrations/001-schema.sql и 002-baseline-guard.sql,
нормализованная 24-табличная модель пока целевая, решение — ADR-015.

Локальная поставка не заменяет реальные соседние сервисы. Receipt mock: — заглушка;
QA iterations=null/PARTIAL до D-09. Расчёт денег не подменяет отсутствующую
методику и ставку; плановая дата до реализации полного рабочего календаря
помечается WORKING_CALENDAR_FINISH/PARTIAL. Нагрузочные NFR, централизованная
телеметрия, Kafka mapping/DLQ и backup/restore общего стенда требуют следующей
итерации. Локальные PostgreSQL restore и minikube/PVC проверяются отдельно ниже.

## Docker Compose

Из корня репозитория:

```sh
docker compose -f planning-system/compose.yaml up --build
```

http://localhost:8080; PostgreSQL внутри сети. Среда dev с синтетическими
данными; API — non-root uid 10001, база и файлы — volumes. Дополнительные
настройки dev — .env.example (не класть реальные секреты в Git).
Остановка: `docker compose -f planning-system/compose.yaml down` сохраняет данные.
`down -v` удаляет только данные этого локального набора; применять для повторной
чистой установки сознательно. Для изолированного имени используйте `-p planning-demo`.

## Проверки без Docker

Python 3.12 или проверенный локальный Python 3.14.3:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r planning-system/server/requirements.txt -r planning-system/scripts/requirements-docs.txt
python planning-system/scripts/validate-docs.py
python -m pytest planning-system/tests -q
python planning-system/scripts/audit-traceability.py
```

Unit/API-прогон по умолчанию использует изолированную SQLite; проверка PostgreSQL
задаётся TEST_DATABASE_URL и должна указывать **отдельную тестовую БД**: fixture
очищает свои records/request_results/audit перед каждым тестом. Не указывать
демонстрационную или общую БД. Локальный старт без контейнера из planning-system:

```sh
APP_ENV=development AUTH_MODE=demo DATABASE_URL=sqlite:///./planning-dev.db DEMO_SEED=true STORAGE_MODE=local uvicorn server.app:app --port 8080
```

SQLite — запасной dev-режим, не доказательство PostgreSQL locking/trigger.
Браузерный тест на чистом Compose-наборе (меняет синтетические данные):

```sh
npm install --prefix /tmp/planning-browser playwright@1.58.2
/tmp/planning-browser/node_modules/.bin/playwright install chromium
PLAYWRIGHT_MODULE=/tmp/planning-browser/node_modules/playwright/index.mjs node planning-system/scripts/check-app.mjs
```

Скриншоты и JSON-отчёт — artifacts/. Прототип проверяется отдельным
scripts/check-prototype.mjs; его результат не подменяет browser test приложения.

## Общий стенд: OIDC и реальные adapters

### Локальная демонстрация OIDC по замечанию 1.1 PR #154

Запуск с `compose.oidc.yaml` описан в README. Keycloak 26.7.4 импортирует
`dev/keycloak-realm.json`; шесть пользователей соответствуют ролям R-01…R-06,
их стабильные sub совпадают с владельцем и руководителем synthetic seed.
Клиент planning-web допускает только Authorization Code + PKCE S256, redirect
http://localhost:8080/ и этот web origin; password grant у него отключён.
Отдельный planning-smoke разрешает password grant только для локальной
автоматической проверки и выдаёт JWT на 5 секунд. В общий realm его не переносить.

```sh
python planning-system/scripts/check-oidc.py
PLAYWRIGHT_MODULE=/tmp/planning-browser/node_modules/playwright/index.mjs node planning-system/scripts/check-oidc-browser.mjs
```

Первый smoke проверяет реальный JWT планировщика (200), отсутствие роли (403),
demo-токен (401) и тот же настоящий JWT после истечения (401). Второй проходит
браузерный redirect, форму Keycloak и PKCE, затем читает workspace API.
Оба запускаются отдельным заданием oidc в CI. Локальные credentials и claims
относятся только к synthetic fixture; реальные HR account IDs ими не заменяются.

Публичный issuer — http://localhost:8081/realms/planning. API читает discovery/JWKS
через внутреннее имя keycloak; issuer в metadata и JWT всё равно сравнивается
с публичным адресом. Для этого добавлены OIDC_DISCOVERY_URL и OIDC_JWKS_URL.
OIDC_LOCAL_HTTP=true допускает HTTP только при APP_ENV=development и только
для localhost/127.0.0.1/keycloak. В staging/production всегда требуется HTTPS,
даже при установленном флаге; unit-регрессии проверяют эту границу.
При переходе с базового Compose пересоздайте api этой же командой; миграции
и seed сохраняют существующий локальный набор. Этот режим не подтверждает
выдачу общих клиентов, S3, Kafka и T-INT-01.

### Конфигурация общего стенда

Compose здесь — dev. Для общего стенда Infra предоставляет конфигурацию по
[160](docs/160.integration-plan.md): APP_ENV=staging, AUTH_MODE=oidc,
OIDC_ISSUER (HTTPS), OIDC_AUDIENCE, OIDC_CLIENT_ID и redirect URI web клиента.
Браузер использует Authorization Code + PKCE/state, API проверяет RS256,
issuer/audience/exp/iat/sub и claims. Требуются portfolio_ids/project_ids/
employee_ids и логические роли из 070; токены сервисов имеют S-03/S-06/S-07 и
publication.read/ack, facts.write, reports.read/export, qa.read соответственно.
Администратор не получает бизнес-права. cost.read и cost.write выдаются отдельно.

Для S3: STORAGE_MODE=s3, S3_ENDPOINT (HTTPS), S3_BUCKET, S3_REGION,
AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY через Secret. Ошибка реального сервиса
возвращает 503, автоматического переключения на mock нет. API отвечает файлом
после проверки прав, force attachment и nosniff.

TT: INTEGRATION_MODE=real, TT_BASE_URL (HTTPS, включая /api/v1), TT_TOKEN,
TT_MAPPING_APPROVED=true только после датированного D-01. Кандидат adapter:
Project/version → PUT /planning/projects/{externalId}, receipt applied/already-applied.
Факт принимается авторизованным POST /integrations/task-events по 140 с inbox,
sourceRevision, tombstone. Реальные Kafka payload и нормы соответствия TT требуют
mapping; этот endpoint не утверждает совместимость внутренних событий TT.
Worker использует durable PENDING/FAILED и 5 повторов; технический retry не меняет
baseline. Реальные события и notification DLQ ещё требуют инфраструктурной стыковки.

CURSOR_SECRET на общем стенде — случайный секрет минимум 32 символа.
ALLOWED_ORIGINS — точные web origins, без wildcard. В production/dev shared
не разрешать demo-переключение, local storage и synthetic seed. Секреты не
публиковать в GitHub Actions артефактах; workflow поставляет только тестовые значения.

## Minikube

Манифест [stand.yaml](deploy/minikube/stand.yaml) относится к **локальному dev**,
использует demo auth/local files; не копировать его на общий staging без
конфигурации Infra. [Secret template](deploy/minikube/secret.template.yaml) пустой.

```sh
minikube image load planning-system:local
kubectl apply -f planning-system/deploy/minikube/stand.yaml
```

Создать planning-secret в namespace arch-planning-system из локального неотслеживаемого
env-файла с DB_PASSWORD, DATABASE_URL=postgresql+psycopg://planning:...@postgres:5432/planning,
CURSOR_SECRET. Не применять пустой template как работающий Secret. Затем:

```sh
kubectl -n arch-planning-system wait --for=condition=complete job/planning-migrate --timeout=120s
kubectl -n arch-planning-system rollout status deployment/planning-api
kubectl -n arch-planning-system port-forward service/planning-api 8080:8000
```

Для Ingress включить addon ingress и добавить planning.local в локальное разрешение
имён на IP minikube. Readiness проверяет миграции/БД; liveness не зависит от соседей.
PostgreSQL PVC сохраняется после перезапуска pod. Фактический minikube/restore
прогон фиксируется отдельно, наличие YAML не считается passed.

Повторяемая проверка отдельного dev-кластера после развёртывания:

```sh
python planning-system/scripts/check-minikube.py --context <имя-dev-кластера> --restart --ingress
```

Нужен включённый addon ingress и доступный kubectl того же minor Kubernetes.
При отдельном kubeconfig задайте KUBECONFIG. Скрипт принимает только
APP_ENV=development/AUTH_MODE=demo, использует собственные синтетические проект
и файл, проверяет Bound PVC, повтор seed, перезапуск postgres-0/API и маршрут
planning.local через ingress-nginx. Порт открывается только на 127.0.0.1 и
закрывается после проверки. JSON-доказательство — artifacts/minikube-report.json.
Инструкция установки — [официальная документация minikube](https://minikube.sigs.k8s.io/docs/start/).

## Локальная резервная копия и восстановление

После browser test, когда уже есть ACTIVE baseline:

```sh
python planning-system/scripts/check-restore.py --project <имя-compose-набора>
```

Проверка требует отдельный синтетический dev-набор. На время сравнения
останавливается только его worker; pg_dump восстанавливается в новую временную
БД. Сверяются records/audit/request_results и неизменяемость baseline, затем
клон удаляется и worker возвращается в исходное состояние. Исходная БД не
заменяется. Отчёт содержит хеш копии и измеренные длительности, без секретов
или содержимого данных. Это проверка локального восстановления; RPO/RTO и
копии S3 на общем стенде принимаются отдельно с Infra.
