# Reference Manager - комплект документов

Комплект по [составу документов курсового проекта](../../task-tracker/docs/documents-composition.md), блоки A-I. Основание - [системные требования](system-requirements.md), [видение](vision.md), [конституция проекта](../.specify/memory/constitution.md) и код в `main`. Описывает проектируемую систему: в репозитории есть каркас сервиса, методы справочников, история, защита API и интерфейс ещё не реализованы.

**Редакция:** 2.0, 2026-09-27. **Статус:** к ревью команды. Изменения 2026-09-27: API по принципам Google AIP, коллекция и методы на каждый справочник, история как ревизии с различиями отдельно на справочник, состав справочников фиксируется один раз без заявок, конституция 3.0.0.

| Блок | Документ | Содержание |
| --- | --- | --- |
| A | [010 - Глоссарий](block-a-context-and-scope/010.glossary.md) | Термины предметной области, контекст, синонимы |
| A | [020 - Контекст системы](block-a-context-and-scope/020.system-context.md) | Границы, внешние системы, акторы, владение данными, расхождения с кодом |
| A | [030 - Акторы](block-a-context-and-scope/030.actors.md) | Люди и внешние системы, их цели |
| B | [040 - Event Storming](block-b-domain-analysis/040.event-storming.md) | Команды, события, агрегаты по процессам |
| B | [050 - Сущности и жизненные циклы](block-b-domain-analysis/050.entities.md) | Справочник, запись, ревизия; статусная модель |
| B | [060 - Use Cases](block-b-domain-analysis/060.use-cases.md) | Диаграммы, спецификации, покрытие FR |
| C | [070 - RBAC](block-c-requirements-and-roles/070.role-matrix.md) | Уровни create, read, update, execute, delete; роли reader и admin |
| C | [075 - NFR](block-c-requirements-and-roles/075.nfr.md) | Метрики, пороги, проверки, связь с ADR |
| C | [080 - администратор](block-c-requirements-and-roles/080.admin-user-stories.md) | US-AD |
| C | [080 - читатель](block-c-requirements-and-roles/080.reader-user-stories.md) | US-RD |
| C | [080 - сервис-потребитель](block-c-requirements-and-roles/080.consumer-service-user-stories.md) | US-CS |
| C | [090 - Эпики](block-c-requirements-and-roles/090.features-epics.md) | Эпики, приоритеты, вехи M4 и M5 |
| D | [095 - Матрица покрытия](block-d-verification/095.requirements-check.md) | Трассировка требований к историям, документам и тестам |
| E | [110 - UI/UX](block-e-ui-ux-design/110.ui-ux.md) | Принципы, экраны, навигация, видимость по ролям |
| E | [115 - Live-прототип](block-e-ui-ux-design/115.live-prototype.md) | Один `index.html` с навигацией по экранам |
| F | [120 - Модель данных](block-f-data-model/120.data-model.md) | ER-диаграмма, таблицы, ограничения, индексы |
| G | [130 - Контракты API](block-g-api-and-events/130.api-contracts.md) | Методы на справочник по AIP, примеры, ошибки, версионирование |
| G | [135 - Каталог событий](block-g-api-and-events/135.event-catalog.md) | Пуст по решению |
| G | [140 - Схемы событий](block-g-api-and-events/140.event-schema.md) | Пуст по решению |
| H | [145 - ADR](block-h-architecture-and-logic/145.architecture-decisions.md) | Реестр решений |
| H | [146 - Логическая схема](block-h-architecture-and-logic/146.logic-scheme.md) | Потоки данных, компоненты, границы |
| H | [150 - Компоненты](block-h-architecture-and-logic/150.component-diagram.md) | C4 Component, технологии, интерфейсы |
| I | [155 - Sequence](block-i-integration-and-deployment/155.sequence-diagrams.md) | Ключевые сценарии |
| I | [160 - План интеграций](block-i-integration-and-deployment/160.integration-plan.md) | Интеграции, вехи, ответственные, критерии |
| I | [165 - Развёртывание](block-i-integration-and-deployment/165.deployment-diagram.md) | Окружения, узлы, порядок выкладки |

## Правила чтения

- Идентификаторы требований FR-RM, INT-RM, BR-RM, NFR-RM взяты из системных требований; отозванные перечислены в их разделе 1.3 и не переиспользуются. Идентификаторы комплекта: акторы H и S, роли R, UC, US, эпики E, ADR, SD, интеграции I, расхождения с кодом K.
- Пометка "срез 2" или "срез 3" означает, что элемент относится к защите API или интерфейсу и не входит в первую версию (раздел 13 требований).
- Документы описывают контракт и модель, а не реализацию: детали хранения приведены только там, где их требует состав документа (120), детали компонентов - в 150.
- Расхождения между требованиями и кодом собраны в [020, раздел 6](block-a-context-and-scope/020.system-context.md); открытые вопросы требований и ответственные - в [160, раздел 3](block-i-integration-and-deployment/160.integration-plan.md).
- Документы 135 и 140 пусты намеренно: сервис не публикует события.
