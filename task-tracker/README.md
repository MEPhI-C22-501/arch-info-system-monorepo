# Task Tracker

Система управления задачами для командной работы: бэклог, канбан-доска, итерации, декомпозиция задач, комментарии, учёт трудозатрат и обмен данными через Excel.

## Реализация

- `backend/` — Java 21, Spring Boot, PostgreSQL и Liquibase: карточки, иерархия, итерации, аудит, уведомления, Excel и защищённые API интеграций.
- `frontend/` — React/TypeScript: бэклог, канбан-доска, карточка, планирование итераций, уведомления и настройки.
- `dev/` — демонстрационный realm Keycloak; `compose.yaml` — локальное окружение.

Запуск из этой папки: `docker compose up --build`. Интерфейс: <http://localhost:3000>, Keycloak: <http://localhost:8081>, API: <http://localhost:8080/api/v1>. Тестовые учётные записи в Keycloak: `member`, `lead`, `admin` с паролем `demo12345`; данные предназначены только для локальной разработки. База и сервисы слушают только loopback. На первом старте миграции создают справочники, а dev-адаптер — тестовых пользователей и локальный допуск.

Проверки: `cd backend && mvn test`; `cd frontend && npm ci && npm test && npm run build`; `docker compose config --quiet`. Для полноценной приёмки запустите контейнеры и пройдите сценарии раздела 10 [требований](docs/system-requirements.md). Состояние контейнеров и миграций нельзя проверить одной только сборкой.

Контракт внешнего справочника остаётся черновиком: без `DIRECTORY_URL` применяется только dev-fixture; для реальной интеграции нужны согласованные URL и сервисный токен (`DIRECTORY_TOKEN`). Обмен с Planning System и выбор Kafka/REST требуют согласования по спецификации 162. Для production отдельно необходимы управление секретами, резервные копии, мониторинг, SLO и испытания нагрузки.

Подробные функциональные требования, бизнес-правила, сценарии и критерии приёмки описаны в [документе требований](docs/system-requirements.md).

## Разработка

Правила структуры проекта и качества кода приведены в [руководстве для участников](AGENTS.md). Для запуска вне Docker задайте `DATABASE_URL`, `DATABASE_USER`, `DATABASE_PASSWORD`, `OIDC_ISSUER_URI`, `OIDC_JWKS_URI`, затем выполните `mvn spring-boot:run` и `npm run dev` в соответствующих модулях.

## Доработка документации по PR #102

[162 — предложения интеграций и реестр согласований](docs/block-i-integration-and-deployment/162.integration-spec.md), [130 — проектные API-контракты](docs/block-g-api-and-events/130.api-contracts.md), [160 — этапы работ](docs/block-i-integration-and-deployment/160.integration-plan.md), [095 — полнота требований](docs/block-d-verification/095.requirements-check.md).

Keycloak принят как единый IdP проекта. Владение данными Planning, выбор Kafka либо REST, формат ETL и параметры общего MinIO требуют подтверждения соответствующими командами согласно 162. Новая реализация интеграций в этот коммит не входит. Проверка существующего прототипа — по [чек-листу](frontend/prototype/CHECKLIST.md).
