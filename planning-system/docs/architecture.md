# Архитектура Planning System

## 1. Архитектурная идея

Planning System - система управленческого планирования, а не еще одна канбан-доска.
Она формирует утвержденные ограничения и прогнозы для портфеля, проектов, людей и
денег. Task Tracker остается системой оперативного исполнения и источником статусов,
затраченного времени и прогресса задач.

Для первой очереди предлагается модульный монолит: он снижает стоимость разработки
и сохраняет транзакционную согласованность версий плана, ресурсов и бюджета.
Интеграции и тяжелые отчеты выполняются отдельными workers. Если профиль нагрузки
это потребует, модули ресурсов, финансов или расчетов можно выделить в сервисы без
изменения доменных границ.

Ключевые свойства решения:

- неизменяемые утвержденные версии и базовые линии;
- единый расчет сроков, мощностей и стоимости;
- сценарии изолированы от активного плана;
- надежный обмен через inbox/outbox и идемпотентные сообщения;
- детализация агрегатов до исходной записи;
- явные владельцы данных и границы со смежными системами.

## 2. C4 Level 1 - System Context

Исходник: [`diagrams/01-c4-context.mmd`](diagrams/01-c4-context.mmd).

```mermaid
flowchart LR
  sponsor["Спонсор / владелец портфеля"]
  planner["PMO / планировщик"]
  pm["Руководитель проекта"]
  resource["Ресурсный руководитель"]
  finance["Финансовый контролер"]
  employee["Участник команды"]

  ps["Planning System<br/>Портфельное, ресурсное, календарное<br/>и финансовое планирование"]

  idp["Keycloak<br/>SSO и учетные записи"]
  tracker["Task Tracker<br/>Задачи, история, итерации, тесты и дефекты"]
  hr["HR-система<br/>Сотрудники, оргструктура, отсутствия"]
  fin["Финансовая система<br/>Обязательства и фактические расходы"]
  ref["Reference Manager<br/>Общие справочники"]
  bi["BI / корпоративная отчетность"]
  notify["Сервис уведомлений"]
  tfs["TFS<br/>Внешний обмен дефектами"]

  sponsor -->|"утверждает портфель и лимиты"| ps
  planner -->|"создает версии и сценарии"| ps
  pm -->|"планирует проект и прогнозирует"| ps
  resource -->|"распределяет мощности"| ps
  finance -->|"контролирует бюджет и источники"| ps
  employee -->|"просматривает назначения"| ps

  ps -->|"аутентификация"| idp
  ps <-->|"планы работ, статусы, часы"| tracker
  ps <-->|"сотрудники, календари, ставки"| hr
  ps <-->|"лимиты, обязательства, факт"| fin
  ps -->|"читает классификаторы"| ref
  ps -->|"публикует витрины/выгрузки"| bi
  ps -->|"отправляет события"| notify
  tracker <-->|"дефекты, статусы, комментарии"| tfs

  classDef person fill:#084c61,color:#fff,stroke:#063645;
  classDef system fill:#2b6cb0,color:#fff,stroke:#1a4971;
  classDef external fill:#e8eef7,color:#172b4d,stroke:#6b7a90;
  class sponsor,planner,pm,resource,finance,employee person;
  class ps system;
  class idp,tracker,hr,fin,ref,bi,notify,tfs external;
```

### Владение мастер-данными

| Данные | Система-источник | Что хранит Planning System |
|---|---|---|
| Пользователь и аутентификация | Keycloak | внешний ID, прикладные роли и область доступа |
| Сотрудник, подразделение, отсутствие | HR | версионируемый снимок для расчета мощности |
| Задача, статус, история, фактические часы, тесты и дефекты | Task Tracker | связь с плановым элементом и снимки факта |
| Валюта, единица, тип финансирования | Reference Manager | стабильный код и отображаемое имя снимка |
| Проводка, обязательство, фактический расход | Финансовая система | нормализованная запись, внешний ID и дата среза |
| Сценарий, версия плана, назначение, бюджет | Planning System | мастер-запись и история решений |

## 3. C4 Level 2 - Containers

Исходник: [`diagrams/02-c4-container.mmd`](diagrams/02-c4-container.mmd).

```mermaid
flowchart TB
  user["Пользователь"]
  ext["Смежные системы"]

  subgraph ps["Planning System"]
    web["Web application<br/>SPA, рабочие места и аналитика"]
    api["Application API<br/>REST/BFF, авторизация, orchestration"]
    core["Planning Core<br/>Портфель, планы, календарь, workflow"]
    res["Resource Planning<br/>Мощности, назначения, конфликты"]
    money["Financial Planning<br/>Источники, бюджет, факт, прогноз"]
    calc["Scenario & Forecast Engine<br/>Пересчет сценариев и показателей"]
    report["Reporting Worker<br/>XLSX/CSV, витрины и тяжелые отчеты"]
    integration["Integration Worker<br/>Inbox/outbox, импорт и синхронизация"]
    db[("PostgreSQL<br/>Транзакционные данные и аудит")]
    objects[("Object Storage<br/>Импорты и сформированные отчеты")]
    broker[("Message Broker<br/>Доменные и интеграционные события")]
  end

  user -->|"HTTPS"| web
  web -->|"JSON/HTTPS"| api
  api --> core
  api --> res
  api --> money
  core --> calc
  res --> calc
  money --> calc
  core --> db
  res --> db
  money --> db
  calc --> db
  api -->|"ставит задания"| broker
  report --> broker
  integration --> broker
  report --> db
  report --> objects
  integration --> db
  integration <-->|"REST / events / files"| ext
```

## 4. C4 Level 3 - Planning Core Components

Исходник:
[`diagrams/03-c4-component-planning-core.mmd`](diagrams/03-c4-component-planning-core.mmd).

```mermaid
flowchart LR
  api["Application API"]
  tracker["Integration Worker / Task Tracker"]
  resource["Resource Planning module"]
  financial["Financial Planning module"]
  broker[("Message Broker")]
  db[("PostgreSQL")]

  subgraph core["Planning Core"]
    portfolio["Portfolio Component<br/>Инициативы, программы, приоритеты"]
    project["Project Component<br/>Проекты, этапы, вехи"]
    version["Plan Version Component<br/>Сценарии и базовые линии"]
    schedule["Scheduling Component<br/>Даты, зависимости, Гант"]
    approval["Approval Component<br/>Маршруты и решения"]
    progress["Progress Component<br/>Снимки статуса и отклонения"]
    outbox["Outbox Component<br/>Надежная публикация событий"]
  end

  api --> portfolio
  api --> project
  api --> version
  api --> approval
  portfolio --> project
  project --> version
  version --> schedule
  version --> approval
  tracker --> progress
  progress --> schedule
  schedule --> resource
  schedule --> financial
  portfolio --> db
  project --> db
  version --> db
  schedule --> db
  approval --> db
  progress --> db
  approval --> outbox
  version --> outbox
  outbox --> broker
```

## 5. UML - доменная модель

Это концептуальная модель, не физическая схема БД. Справочники, аудит и технические
таблицы опущены. Исходник:
[`diagrams/04-uml-domain-model.mmd`](diagrams/04-uml-domain-model.mmd).

```mermaid
classDiagram
  class Portfolio
  class Project
  class PlanVersion {
    +Integer version
    +PlanStatus status
    +Instant dataAsOf
  }
  class PlanItem {
    +ItemType type
    +Decimal plannedHours
    +Date start
    +Date finish
  }
  class Dependency {
    +DependencyType type
    +Integer lagDays
  }
  class ResourceDemand {
    +Role role
    +Grade grade
    +Decimal hours
  }
  class Allocation {
    +UUID employeeId
    +Decimal hours
  }
  class FundingSource {
    +String type
    +String currency
    +Decimal limit
  }
  class BudgetVersion {
    +BudgetStatus status
    +Instant dataAsOf
  }
  class BudgetLine {
    +CostCategory category
    +Period period
    +Decimal amount
  }
  class ActualCost {
    +UUID externalId
    +Decimal amount
    +Date postingDate
  }
  class ApprovalDecision

  Portfolio "1" o-- "0..*" Project
  Project "1" *-- "1..*" PlanVersion
  PlanVersion "1" *-- "0..*" PlanItem
  PlanItem "1" --> "0..*" Dependency : predecessor
  PlanItem "1" *-- "0..*" ResourceDemand
  ResourceDemand "1" o-- "0..*" Allocation
  Project "1" o-- "1..*" FundingSource
  Project "1" *-- "1..*" BudgetVersion
  BudgetVersion "1" *-- "0..*" BudgetLine
  FundingSource "1" <-- "0..*" BudgetLine : funded by
  BudgetLine "1" o-- "0..*" ActualCost
  PlanVersion "1" o-- "0..*" ApprovalDecision
  BudgetVersion "1" o-- "0..*" ApprovalDecision
```

## 6. UML - годовое планирование

Исходник:
[`diagrams/06-uml-sequence-annual-planning.mmd`](diagrams/06-uml-sequence-annual-planning.mmd).

```mermaid
sequenceDiagram
  autonumber
  actor PMO as PMO / планировщик
  participant PS as Planning System
  participant HR as HR-система
  participant TT as Task Tracker
  participant FS as Финансовая система
  actor RM as Ресурсный руководитель
  actor FC as Финансовый контролер
  actor SP as Спонсор

  PMO->>PS: Создать годовой сценарий портфеля
  PS->>HR: Получить оргструктуру, календари и мощности
  HR-->>PS: Актуальные данные с датой среза
  PS->>TT: Получить незавершенные работы и факт
  TT-->>PS: Задачи, прогресс, трудозатраты
  PS->>FS: Получить лимиты, обязательства и факт
  FS-->>PS: Финансовый срез
  PS->>PS: Рассчитать сроки, потребность, стоимость и дефициты
  PS-->>PMO: Сравнение сценариев и предупреждения
  PMO->>RM: Направить ресурсную часть на согласование
  RM-->>PS: Подтвердить мощности / вернуть замечания
  PMO->>FC: Направить бюджет на согласование
  FC-->>PS: Подтвердить источники / вернуть замечания
  PMO->>SP: Направить целевой сценарий
  SP-->>PS: Утвердить план
  PS->>PS: Зафиксировать неизменяемую базовую линию
  PS-->>TT: Опубликовать утвержденные плановые рамки
```

## 7. UML - перепланирование по факту

Исходник:
[`diagrams/07-uml-sequence-replanning.mmd`](diagrams/07-uml-sequence-replanning.mmd).

```mermaid
sequenceDiagram
  autonumber
  participant TT as Task Tracker
  participant IW as Integration Worker
  participant PS as Planning Core
  participant CE as Scenario Engine
  actor PM as Руководитель проекта
  actor AP as Согласующий

  TT-->>IW: TaskProgressChanged / TimeLogged
  IW->>IW: Проверить idempotency key
  IW->>PS: Обновить снимок факта
  PS->>CE: Пересчитать прогноз и влияние
  CE-->>PS: Новые даты, EAC, дефициты и зависимости
  PS-->>PM: Предупреждение об отклонении
  PM->>PS: Создать сценарий перепланирования
  PS->>CE: Рассчитать варианты
  CE-->>PM: Сравнение сроков, ресурсов и бюджета
  PM->>PS: Отправить выбранный вариант на согласование
  PS-->>AP: Запрос решения
  AP->>PS: Утвердить
  PS->>PS: Создать новую активную версию и сохранить старую
  PS-->>IW: PlanActivated
  IW-->>TT: Обновить плановые рамки задач
```

## 8. UML - жизненный цикл версии плана

Исходник: [`diagrams/08-uml-plan-state.mmd`](diagrams/08-uml-plan-state.mmd).

```mermaid
stateDiagram-v2
  [*] --> DRAFT
  DRAFT --> ON_REVIEW: отправить на согласование
  ON_REVIEW --> DRAFT: вернуть на доработку
  ON_REVIEW --> APPROVED: все обязательные решения получены
  APPROVED --> ACTIVE: ввести в действие
  ACTIVE --> SUPERSEDED: активирована новая версия
  DRAFT --> ARCHIVED: отменить черновик
  APPROVED --> ARCHIVED: отменить до активации
  SUPERSEDED --> ARCHIVED: завершить срок хранения online
  ARCHIVED --> [*]
```

## 9. Дополнительные представления

- [UML use cases](diagrams/05-uml-use-cases.mmd) - роли и основные варианты
  использования;
- [Deployment view](diagrams/09-deployment.mmd) - предварительная схема
  промышленного развертывания.

## 10. Модульные границы

| Модуль | Владеет | Не владеет |
|---|---|---|
| Portfolio | инициативы, программы, приоритеты, решения портфеля | задачи исполнения, кадровые карточки |
| Planning Core | проекты, версии, сценарии, плановые элементы, зависимости, baseline | фактические часы и проводки |
| Resource Planning | потребности, снимки мощности, назначения, конфликты | кадровая мастер-запись сотрудника |
| Financial Planning | источники финансирования, версии бюджета, строки плана, EAC | бухгалтерская мастер-проводка |
| Approval | экземпляры маршрутов и решения | корпоративные учетные записи |
| Integration | inbox/outbox, сопоставление ID, снимки и протоколы синхронизации | бизнес-правила источников |
| Reporting | проекции, выгрузки, отчеты | изменение бизнес-сущностей |

## 11. Интеграционные события первой очереди

- исходящие: `ProjectPlanned`, `PlanSubmitted`, `PlanApproved`, `PlanActivated`,
  `AllocationChanged`, `FundingLimitExceeded`, `BudgetForecastChanged`;
- входящие: `EmployeeChanged`, `AbsenceChanged`, `TaskChanged`, `TaskHistoryChanged`,
  `TimeLogged`, `TestRunChanged`, `DefectChanged`, `FinancialActualPosted`,
  `FundingLimitChanged`, `ReferenceItemChanged`.

Каждое сообщение должно иметь `eventId`, `eventType`, `occurredAt`, `producer`,
`schemaVersion`, `correlationId` и полезную нагрузку. Обработчик обязан хранить
результат обработки `eventId` для защиты от повторной доставки.

## 12. Основные риски архитектуры

| Риск | Мера |
|---|---|
| Несогласованные идентификаторы систем | таблица сопоставления, стабильные внешние ID, сверка импорта |
| Двойной учет часов или денег | четкое владение данными, idempotency, дата среза, детализация до источника |
| Медленный пересчет больших сценариев | фоновые задания, инкрементальный расчет, профилирование на нагрузочном прототипе |
| Неконтролируемое изменение истории | immutable approved versions, audit log, новая версия вместо правки |
| Избыточное раннее дробление на микросервисы | модульный монолит и контролируемые границы транзакций первой очереди |
| Разрыв между планом и задачами | события, мониторинг задержки синхронизации и отчет расхождений |
