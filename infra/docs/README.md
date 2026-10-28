# Документы инфраструктуры

Vision остаётся в [../vision.md](../vision.md). Здесь — детализация, которую можно проверять отдельно от обзора.

| Файл | Содержание |
| --- | --- |
| [010.glossary.md](010.glossary.md) | Термины и владение данными |
| [070.role-matrix.md](070.role-matrix.md) | Пользователи, OIDC, Kafka, S3 и БД |
| [078.quality-scenarios.md](078.quality-scenarios.md) | Сценарии качества и взвешенная матрица четырёх видов |
| [130.api-contracts.md](130.api-contracts.md) | Каталог OpenAPI |
| [135.event-catalog.md](135.event-catalog.md) | Внешние события |
| [140.event-schema.md](140.event-schema.md) | Envelope, DLQ и совместимость |
| [145.architecture-decisions.md](145.architecture-decisions.md) | ADR |
| [146.logic-scheme.md](146.logic-scheme.md) | Синхронные, асинхронные и пакетные связи |
| [150.component-diagram.md](150.component-diagram.md) | Компоненты и интерфейсы |
| [155.sequence-diagrams.md](155.sequence-diagrams.md) | Сквозные сценарии |
| [160.integration-plan.md](160.integration-plan.md) | Зависимости и приёмка |
| [162.integration-spec.md](162.integration-spec.md) | Выбор способа обмена |
| [165.deployment-diagram.md](165.deployment-diagram.md) | Compose и minikube |
| [rework-status.md](rework-status.md) | Замечание ревью, артефакт и проверка |

Статусы: `draft`, `agreed`, `implemented`, `verified`. Документ и успешный `docker compose config` сами по себе не переводят интеграцию в `verified`.
