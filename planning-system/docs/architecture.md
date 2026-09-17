# Архитектура Planning System

## 1. Принципы

- Planning System является мастер-системой проектов и плановых версий.
- Task Tracker является мастер-системой задач и факта их исполнения.
- Keycloak используется как готовый компонент аутентификации; отдельный сервис входа
  не создается.
- Интеграции с авторизацией, справочниками, оповещениями, вложениями и Task Tracker
  входят в первую версию.
- Утвержденная версия плана неизменна.
- Обмен выполняется через версионированные API и идемпотентные события.

## 2. C4 Context

```mermaid
flowchart LR
  user["Пользователи Planning System"] --> ps["Planning System<br/>Проекты, ресурсы, сроки и прогноз"]
  ps -->|"OIDC"| kc["Keycloak"]
  ps <-->|"справочники"| ref["Reference Manager"]
  ps -->|"проекты и плановые рамки"| tt["Task Tracker"]
  tt -->|"задачи и факт исполнения"| ps
  ps -->|"запросы оповещений"| ns["Notification Service"]
  ps <-->|"файлы"| os["Object Storage"]
  ps -->|"проекции"| rpt["Reporting"]
```

## 3. C4 Containers

```mermaid
flowchart TB
  web["Web application"] --> api["Application API"]
  api --> core["Planning Core<br/>Проекты, версии, календарь"]
  api --> resource["Resource Planning<br/>Доступность и назначения"]
  core --> forecast["Forecast Engine<br/>Скользящий прогноз и сценарии"]
  api --> attach["Attachment Component"]
  api --> notify["Notification Component"]
  core --> db[("PostgreSQL")]
  resource --> db
  forecast --> db
  attach --> storage[("Object Storage")]
  integration["Integration Worker"] --> db
  integration --> broker[("Message Broker")]
  notify --> broker
```

## 4. Компоненты Planning Core

```mermaid
flowchart LR
  portfolio["Portfolio<br/>Проекты и приоритеты"] --> version["Plan Version<br/>Версии и baseline"]
  version --> schedule["Scheduling<br/>Даты и зависимости"]
  schedule --> capacity["Capacity<br/>Роли, грейды и назначения"]
  schedule --> forecast["Forecast<br/>Остаток и корректировки"]
  version --> approval["Approval<br/>Решения"]
  version --> publication["Publication<br/>Передача проектов в Task Tracker"]
  progress["Task Progress<br/>События задач"] --> forecast
  progress --> notification["Notification<br/>Оповещения"]
  attachment["Attachment<br/>Метаданные файлов"] --> portfolio
  attachment --> version
```

## 5. Доменная модель

```mermaid
classDiagram
  class Project
  class PlanVersion {
    +version
    +status
    +dataAsOf
  }
  class PlanItem {
    +type
    +plannedHours
    +start
    +finish
  }
  class ResourceDemand {
    +role
    +grade
    +hours
  }
  class Allocation {
    +employeeId
    +hours
    +period
  }
  class TaskSnapshot {
    +externalTaskId
    +status
    +actualHours
    +changedAt
  }
  class ForecastSnapshot {
    +remainingHours
    +remainingDuration
    +budgetAdjustment
  }
  class Attachment {
    +objectKey
    +fileName
    +contentType
    +uploadedBy
  }

  Project "1" *-- "1..*" PlanVersion
  PlanVersion "1" *-- "0..*" PlanItem
  PlanItem "1" *-- "0..*" ResourceDemand
  ResourceDemand "1" o-- "0..*" Allocation
  Project "1" o-- "0..*" TaskSnapshot
  PlanVersion "1" o-- "0..*" ForecastSnapshot
  Project "1" o-- "0..*" Attachment
  PlanVersion "1" o-- "0..*" Attachment
```

## 6. Интеграционные события

Исходящие: `ProjectCreated`, `ProjectChanged`, `PlanActivated`,
`AllocationChanged`, `RemainingForecastChanged`, `BudgetAdjustmentChanged`,
`NotificationRequested`.

Входящие: `TaskCreated`, `TaskChanged`, `TaskCommented`, `TimeLogged`,
`NotificationDelivered`, `ReferenceItemChanged`.

Каждое событие содержит `eventId`, `eventType`, `occurredAt`, `producer`,
`schemaVersion`, `correlationId` и идентификатор проекта Planning System.

## 7. Развертывание

Система использует общую инфраструктуру проекта: Keycloak, PostgreSQL, брокер
сообщений, Object Storage, централизованные журналы, метрики и трассировку. Секреты
задаются средствами среды развертывания и не хранятся в репозитории.
