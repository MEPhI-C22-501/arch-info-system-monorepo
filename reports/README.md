# Reports — подсистема отчётности

Подсистема Reports формирует отчёты по трудозатратам, ресурсам, срокам, дефектам,
тестированию и качеству релизов для системы «Трекер задач».

Подсистема состоит из двух контуров: оперативного (оперативная витрина и её
read-replica, оперативные дашборды) и аналитического (ETL, хранилище DWH, кубы OLAP,
аналитические отчёты).

## Документы

Комплект и правила чтения — [docs/README.md](docs/README.md). Состояние на 2026-10-25:

| Блок | Документы | Статус |
| --- | --- | --- |
| — | [Vision](docs/vision.md) | Редакция 0.3, актуальные интеграционные ограничения — [020, раздел 7](docs/020.system-context.md#7-расхождения-vision-с-документами-соседей) |
| A | [010](docs/010.glossary.md), [020](docs/020.system-context.md), [030](docs/030.actors.md) | Написаны, к ревью |
| B | [040](docs/040.event-storming.md), [050](docs/050.entities.md), [060](docs/060.use-cases.md) | Написаны, к ревью |
| C | [070](docs/070.role-matrix.md), [075](docs/075.nfr.md), 080 — семь файлов, [090](docs/090.features-epics.md) | Написаны, к ревью |
| D | [095](docs/095.requirements-check.md) | Написан, к ревью |
| E | [110](docs/110.ui-ux.md), [115](docs/115.live-prototype.md), [прототип](prototype/index.html) | Написаны, к ревью |
| F | [120](docs/120.data-model.md) | Написан, к ревью |
| G | [130](docs/130.api-contracts.md) и [OpenAPI](api/openapi/v1/openapi.yaml), [135](docs/135.event-catalog.md), [140](docs/140.event-schema.md) и [схемы событий](docs/contracts/events/) | Написаны, к ревью; контракты — `draft` до согласования |
| H | [145](docs/145.architecture-decisions.md), [146](docs/146.logic-scheme.md), [150](docs/150.component-diagram.md) | Написаны, к ревью; стек — предложение (Q-REP-15) |
| I | [155](docs/155.sequence-diagrams.md), [160](docs/160.integration-plan.md), [162](docs/162.integration-spec.md), [165](docs/165.deployment-diagram.md) | Написаны, к ревью |
| — | [Проверка безопасности](docs/security-check.md) | Часть проверок пилота автоматизирована; ограничения указаны в отчёте |

«Написан» означает, что артефакт есть, а не что контракты согласованы с соседями:
открытые договорённости — в [020, раздел 6](docs/020.system-context.md#6-открытые-договорённости).

## Рабочие примеры

[Пилоты и запуск](pilots/README.md): ETL, ограниченный API R-01, конфигурации Superset/Keycloak и Cube. [План реализации](docs/implementation-plan.md) отделяет исполняемый объём от целевой системы. Локальный Docker-стенд Superset/Keycloak проверен: [протокол BI](pilots/artifacts/bi-verification.json), скриншоты и ограничения — в инструкции пилотов.

Изменения по проверке от 12.10 и границы приёмки — [реестр замечаний](docs/review-status.md).
Фактическое покрытие T-01…T-35 — [матрица тестов](docs/test-evidence.md),
команды полного локального прогона — [инструкция CI](ci/README.md).

Рабочий [Reports UI](http://localhost:8081/ui/) и [описание R-01…R-11](docs/product-implementation.md): CSV/XLSX, печать, представления, подписки, уведомления и аудит.

## Что ещё не сделано

- Приёмка на общем стенде, Cubestore, холодный режим и повтор нагрузки — [090, раздел 3](docs/090.features-epics.md#3-пилоты-этапа-2).
- Общие Kafka/ACL, read-replica, MinIO, Kubernetes и зарегистрированный CI/CD; приёмка на реальных источниках. Звезда, меры Cube и локальные ops/Kafka реализованы: [описание](docs/star-events-implementation.md).
- Подтверждение договорённостей Q-REP соседями, Infra и преподавателем.
