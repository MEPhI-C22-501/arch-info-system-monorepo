# Planning System — комплект 010–165

Редакция 2.0, 05.10.2026. Доработка по замечаниям от 01.10.2026.
База: main 2d82b9e. Все 24 позиции состава написаны; статус «к ревью» означает
наличие артефакта, не принятие контракта или готовое приложение. План закрытия:
документное ревью до конца проектирования, согласование зависимостей до их
реализации, фактическая приёмка на тестировании по [160](160.integration-plan.md).

| Блок | Документ | Статус |
| --- | --- | --- |
| A | [010 — Глоссарий](010.glossary.md) | Написан, к ревью |
| A | [020 — Контекст и единая матрица обмена](020.system-context.md) | Написан, к ревью |
| A | [030 — Акторы](030.actors.md) | Написан, к ревью |
| B | [040 — Event Storming](040.event-storming.md) | Написан, к ревью |
| B | [050 — Сущности и lifecycle](050.entities.md) | Написан, к ревью |
| B | [060 — Use Cases и Activity](060.use-cases.md) | Написан, к ревью |
| C | [070 — Матрица прав](070.role-matrix.md) | Написан, к ревью |
| C | [075 — NFR](075.nfr.md) | Написан, к ревью |
| C | [080 — User stories по шести ролям (20 историй)](080.administrator-user-stories.md) | Написан, к ревью |
| C | [090 — Эпики по этапам проекта](090.features-epics.md) | Написан, к ревью |
| D | [095 — Покрытие и тестовые спецификации](095.requirements-check.md) | Написан, к ревью |
| E | [110 — UI/UX](110.ui-ux.md) | Написан, к ревью |
| E | [115 — Кликабельный прототип](115.live-prototype.md) | Написан, к ревью |
| F | [120 — Модель БД](120.data-model.md) | Написан, к ревью |
| G | [130 — API и OpenAPI](130.api-contracts.md) | Написан, к ревью |
| G | [135 — Каталог событий](135.event-catalog.md) | Написан, к ревью |
| G | [140 — JSON Schema событий](140.event-schema.md) | Написан, к ревью |
| H | [145 — Журнал ADR](145.architecture-decisions.md) | Написан, к ревью |
| H | [146 — Логическая схема](146.logic-scheme.md) | Написан, к ревью |
| H | [150 — Компоненты](150.component-diagram.md) | Написан, к ревью |
| I | [155 — Последовательности](155.sequence-diagrams.md) | Написан, к ревью |
| I | [160 — План интеграции](160.integration-plan.md) | Написан, к ревью |
| I | [162 — Обоснование интеграций](162.integration-spec.md) | Написан, к ревью |
| I | [165 — Развёртывание и технический backlog](165.deployment-diagram.md) | Написан, к ревью |

Группа 080: [портфель](080.portfolio-owner-user-stories.md),
[планировщик](080.planner-user-stories.md), [руководитель проекта](080.project-manager-user-stories.md),
[ресурсы](080.resource-manager-user-stories.md), [участник](080.team-member-user-stories.md),
[администратор](080.administrator-user-stories.md). Статус всех — к ревью.

## Использование и проверка

[Открыть HTML-прототип](../ui/prototype/index.html). Он работает локально с
синтетическими данными; ограничения и сценарии — 115.
[OpenAPI](contracts/openapi.json), [пример TT-приёмника](contracts/task-tracker-receiver.openapi.json),
схемы/примеры событий в contracts/events и модель таблиц в contracts/data-model.json.
Генераторы 120/130/135/140 находятся в ../scripts; изменения сначала в источнике,
затем повторная генерация. [Проверка](../scripts/validate-docs.py) проверяет ссылки,
состав, OpenAPI и JSON Schema с примерами; результаты ревью — [rework-status](rework-status.md).

## Пояснительные основания

[Vision](vision.md), [ТЗ](technical-specification.md), [архитектура](architecture.md),
[ландшафт](system-landscape.md) и прежние diagrams/*.mmd сохранены как legacy-
основания. Они не заменяют нумерованные отчётные документы. При расхождении
уточнения и открытые решения фиксируются в 020/145/160, не считаются согласованными
самим фактом записи. Reports — подсистема отчётности, единое имя во всём комплекте.

Смежные источники: [Reference Manager](../../reference-manager/documents/system-requirements.md),
[его HR API](../../reference-manager/documents/130.api-contracts.md),
[Task Tracker](../../task-tracker/docs/vision.md), [Reports](../../reports/docs/vision.md),
[QA System](../../qa/docs/vision.md), [Infra](../../infra/vision.md).
В 095: 45 требований, 17 covered / 28 partial / 0 missing по полноте документации.
Приложение и интеграции не объявлены испытанными; список оставшихся согласований
D-01…D-09 и технических поставок виден в 160/165.
