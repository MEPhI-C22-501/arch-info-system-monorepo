# Task Tracker

Система управления задачами для командной работы: бэклог, канбан-доска, итерации, декомпозиция задач, комментарии, учёт трудозатрат и обмен данными через Excel.

## Реализация

- `backend/` — Java 21, Spring Boot, PostgreSQL и Liquibase: карточки, иерархия, итерации, аудит, уведомления, Excel и защищённые API интеграций.
- `frontend/` — React/TypeScript: бэклог, канбан-доска, карточка, планирование итераций, уведомления и настройки.
- `dev/` — демонстрационный realm Keycloak; `compose.yaml` — локальное окружение.

Запустите `docker compose up --build --wait` из этой папки. Интерфейс доступен на <http://localhost:3000>, Keycloak на <http://localhost:8081>, API на <http://localhost:8080/api/v1>. В локальном realm доступны `member`, `lead`, `admin` с паролем `demo12345`. На первом старте миграции создают справочники, а dev-адаптер заполняет кэш тестовых пользователей.

### Данные для демонстрации

После запуска загрузите вымышленные карточки и трудозатраты на выделенном демостенде. Повторный запуск сохраняет существующие записи с теми же ID.

```sh
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U task_tracker -d task_tracker < dev/demo.sql
```

Для общего Compose выполните из корня репозитория после готовности Task Tracker.

```sh
docker compose -f compose.yaml -f compose.modules.yaml --profile modules exec -T task-tracker-db \
  psql -v ON_ERROR_STOP=1 -U task_tracker -d task_tracker < task-tracker/dev/demo.sql
```

На доске появятся две задачи с оценками 8 и 4 часа, а в отчётном API — запись на 2 часа. В бэклоге доступны их проект и эпик, а на вкладке «Итерации» — демо-итерация. Фикстура заполняет БД для демонстрации REST и интерфейса. Для проверки отправки Kafka создайте или измените задачу через приложение.

### База без журнала Liquibase

Для одноразового стенда используйте новое имя проекта, например `docker compose -p tracker-clean up --build --wait` после остановки предыдущего стенда. Docker создаст новый том и сохранит прежний. Для переноса записей из старой базы используйте [порядок восстановления](docs/block-i-integration-and-deployment/167.legacy-database.md).

Проверки: `cd backend && mvn test`; `cd frontend && npm ci && npm test && npm run build`; `docker compose config --quiet`. Для полноценной приёмки запустите контейнеры и пройдите сценарии раздела 10 [требований](docs/system-requirements.md). Состояние контейнеров и миграций нельзя проверить одной только сборкой.

Для подключения справочников задайте `DIRECTORY_URL`, `DIRECTORY_TOKEN_URL` и `DIRECTORY_CLIENT_SECRET` для клиента `tracker-directory`. В локальном режиме без `DIRECTORY_URL` кэш заполняется при `DEV_DIRECTORY=true`. Текущие границы интеграций описаны в [спецификации 168](docs/block-i-integration-and-deployment/168.consumer-contracts.md).

Подробные функциональные требования, бизнес-правила, сценарии и критерии приёмки описаны в [документе требований](docs/system-requirements.md).

## Разработка

Правила структуры проекта и качества кода приведены в [руководстве для участников](AGENTS.md). Для запуска вне Docker задайте `DATABASE_URL`, `DATABASE_USER`, `DATABASE_PASSWORD`, `OIDC_ISSUER_URI`, `OIDC_JWKS_URI`, затем выполните `mvn spring-boot:run` и `npm run dev` в соответствующих модулях.

## Доработка документации по PR #102

[162 — предложения интеграций и реестр согласований](docs/block-i-integration-and-deployment/162.integration-spec.md), [130 — проектные API-контракты](docs/block-g-api-and-events/130.api-contracts.md), [160 — этапы работ](docs/block-i-integration-and-deployment/160.integration-plan.md), [095 — полнота требований](docs/block-d-verification/095.requirements-check.md).

Keycloak принят как единый IdP проекта. Владение данными Planning, выбор Kafka либо REST, формат ETL и параметры общего MinIO требуют подтверждения соответствующими командами согласно 162. Новая реализация интеграций в этот коммит не входит. Проверка существующего прототипа — по [чек-листу](frontend/prototype/CHECKLIST.md).

## Исправления по проверке 12.10.2026

Добавлены [CI и демо-данные](docs/block-i-integration-and-deployment/165.deployment-diagram.md), [отчёт безопасности](docs/security-check.md); временный REST-опрос и контрольные даты согласований уточнены в [162](docs/block-i-integration-and-deployment/162.integration-spec.md). Линтеры: `cd backend && mvn checkstyle:check`; `cd frontend && npm run lint`.

## Правки по разбору 01.11.2026

Перечень изменений, API и параметры интеграций: [отчёт](docs/review-2026-11-01.md).
Проверки: `bash scripts/check.sh`. Для браузерных сценариев поднимите отдельный стенд,
затем выполните `cd frontend && npm run test:e2e`. Переменная `TRACKER_E2E_URL` задаёт
адрес стенда; `TRACKER_CHROME_PATH` позволяет использовать установленный Chromium/Chrome.

## Для команды инфраструктуры

[166 — Настройка S3 и Kafka для Task Tracker](docs/block-i-integration-and-deployment/166.infrastructure-s3-kafka.md) описывает ресурсы, ACL, секреты и параметры подключения.
