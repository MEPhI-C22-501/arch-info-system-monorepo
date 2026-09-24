# Reference Manager - комплект документов

Комплект по составу документов курсового проекта (блоки A-I). Основание - [системные требования](system-requirements.md) и [видение](vision.md) сервиса, [конституция проекта](../.specify/memory/constitution.md), код в `main`. Описывает проектируемую систему: в репозитории есть каркас сервиса (конфигурация, журналирование, клиент PostgreSQL, middleware, служебные точки), а пять операций справочника, телеметрия, защита API и интерфейс ещё не реализованы.

**Редакция:** 1.0, 2026-09-25. **Статус:** к ревью команды.

| Блок | Документ | Содержание |
| --- | --- | --- |
| A | [010 - Глоссарий](block-a-context-and-scope/010.glossary.md) | Термины НСИ, соответствие терминам смежных модулей, выведенные термины |
| A | [020 - Контекст системы](block-a-context-and-scope/020.system-context.md) | Границы, внешние системы, владение данными, расхождения с кодом K-01..K-07 |
| A | [030 - Акторы](block-a-context-and-scope/030.actors.md) | Люди H-01..H-04, внешние системы S-01..S-04 |
| B | [040 - Event Storming](block-b-domain-analysis/040.event-storming.md) | Команды, события, агрегаты по процессам; событий наружу нет |
| B | [050 - Сущности и жизненные циклы](block-b-domain-analysis/050.entities.md) | Справочник, запись, общие столбцы, инварианты, состояния ACTIVE и DELETED |
| B | [060 - Use Cases](block-b-domain-analysis/060.use-cases.md) | UC-01..UC-14, диаграммы, спецификации, покрытие FR |
| C | [070 - RBAC](block-c-requirements-and-roles/070.role-matrix.md) | Роли R-00..R-03, матрица операций, права в базе |
| C | [075 - NFR](block-c-requirements-and-roles/075.nfr.md) | Метрики, пороги, проверки, связь с ADR |
| C | [080 - администратор](block-c-requirements-and-roles/080.admin-user-stories.md) | US-AD-01..08 |
| C | [080 - читатель](block-c-requirements-and-roles/080.reader-user-stories.md) | US-RD-01..05 |
| C | [080 - команда-заказчик](block-c-requirements-and-roles/080.requester-team-user-stories.md) | US-RQ-01..04 |
| C | [080 - сервис-потребитель](block-c-requirements-and-roles/080.consumer-service-user-stories.md) | US-CS-01..05 |
| C | [090 - Эпики](block-c-requirements-and-roles/090.features-epics.md) | E-01..E-10, приоритеты, вехи M4 и M5 |
| D | [095 - Матрица покрытия](block-d-verification/095.requirements-check.md) | Трассировка FR, INT, BR, NFR к UC, историям и тестам |
| E | [110 - UI/UX](block-e-ui-ux-design/110.ui-ux.md) | Экраны S-01..S-04, навигация, видимость по ролям |
| E | [115 - Прототип](block-e-ui-ux-design/115.live-prototype.md) | Состояние и план прототипа |
| F | [120 - Модель данных](block-f-data-model/120.data-model.md) | Таблица на справочник, общие столбцы, индексы, пример миграции, роли базы |
| G | [130 - Контракты API](block-g-api-and-events/130.api-contracts.md) | Пять операций, параметры, ошибки, примеры, версионирование |
| G | [135 - Каталог событий](block-g-api-and-events/135.event-catalog.md) | Пуст по решению; несогласованные ожидания |
| G | [140 - Схемы событий](block-g-api-and-events/140.event-schema.md) | Пуст по решению; что заменяет события |
| H | [145 - ADR](block-h-architecture-and-logic/145.architecture-decisions.md) | ADR-001..012 |
| H | [146 - Логическая схема](block-h-architecture-and-logic/146.logic-scheme.md) | Потоки, слои, соответствие коду |
| H | [150 - Компоненты](block-h-architecture-and-logic/150.component-diagram.md) | Контейнеры и компоненты, интерфейсы |
| I | [155 - Sequence](block-i-integration-and-deployment/155.sequence-diagrams.md) | SD-01..SD-06 |
| I | [160 - План интеграций](block-i-integration-and-deployment/160.integration-plan.md) | I-01..I-10, вехи И-M1..И-M5, согласования |
| I | [165 - Развёртывание](block-i-integration-and-deployment/165.deployment-diagram.md) | Окружения, узлы, порядок выкладки |

## Правила чтения

- Идентификаторы требований FR-RM, INT-RM, BR-RM, NFR-RM взяты из [системных требований](system-requirements.md) без изменений; отозванные не переиспользуются. Идентификаторы комплекта: акторы H и S, роли R, UC, US, эпики E, ADR, SD, интеграции I, расхождения K.
- Пометка "срез 2" или "срез 3" означает, что элемент относится к защите API или интерфейсу и не входит в первую версию (раздел 13 требований).
- Проектные уточнения, которых нет в требованиях (ссылки по `code`, состав столбцов образцовых справочников, лимиты), помечены в тексте и ждут подтверждения.
- Расхождения между требованиями и кодом собраны в [020, раздел 6](block-a-context-and-scope/020.system-context.md); открытые вопросы 1-17 требований и ответственные - в [160, раздел 3](block-i-integration-and-deployment/160.integration-plan.md). Ни один из них документами не решён.
- Состав комплекта соответствует `documents-composition.md` Task Tracker; каталоги блоков названы так же. Документы 135 и 140 намеренно пусты: сервис не публикует события.
