# Vision: Planning System

**Версия:** 1.1
**Статус:** финальная
**Дата:** 21.09.2026

## 1. Видение

Planning System формирует единый реализуемый план проектов с учетом приоритетов,
трудоемкости, доступности людей и календарных ограничений. Система отвечает на
вопросы: какие проекты выполнять, когда, каким составом и как изменится общий план
при отклонении факта.

Planning System хранит проекты. Task Tracker получает проекты и плановые рамки из
Planning System, ведет задачи и возвращает данные об исполнении.

## 2. Пользователи

| Роль | Ответственность |
|---|---|
| Руководитель портфеля | выбирает проекты и утверждает целевой план |
| Планировщик / PMO | формирует годовой и скользящий планы, сравнивает сценарии |
| Руководитель проекта | декомпозирует проект и актуализирует прогноз |
| Ресурсный руководитель | подтверждает доступность и назначения сотрудников |
| Участник команды | просматривает свои назначения и календарь |
| Администратор | настраивает роли, справочники и интеграции |

## 3. Ключевые возможности

1. Годовое и скользящее планирование портфеля проектов.
2. Декомпозиция проекта на этапы, вехи, эпики и фичи.
3. Оценка трудоемкости и потребности по ролям и грейдам.
4. Назначение сотрудников с учетом календарей и доступности.
5. Диаграммы Ганта по проектам и людям.
6. Версии плана, базовые линии и сценарии «что если».
7. Расчет влияния переносов на зависимости и загрузку.
8. Единый прогноз оставшегося времени и бюджетных корректировок.
9. Вложения к проектам, версиям планов и сценариям.
10. Оповещения о создании и изменении связанных задач, конфликтах и решениях.
11. Отчеты по срокам, загрузке, дефициту и отклонениям.

## 4. Ключевые процессы

### 4.1. Формирование плана

Планировщик создает проекты, декомпозирует их, задает оценки по ролям и грейдам.
Система сопоставляет потребность с доступностью людей, строит календарь и выявляет
конфликты. Пользователь сравнивает сценарии, выбирает вариант и утверждает базовую
линию. После утверждения проекты и плановые рамки публикуются в Task Tracker.

```mermaid
flowchart LR
  A["Создание проектов"] --> B["Этапы, эпики и фичи"]
  B --> C["Часы, роли и грейды"]
  C --> D["Доступность и назначения"]
  D --> E{"Есть конфликт?"}
  E -->|"да"| F["Сценарий: перенос, замена или изменение объема"]
  F --> D
  E -->|"нет"| G["Календарь и Гант"]
  G --> H["Утверждение базовой линии"]
  H --> I["Публикация проектов в Task Tracker"]
```

### 4.2. Скользящее перепланирование

Task Tracker передает события создания и изменения задач, статусы, историю и
фактическую трудоемкость. Planning System сравнивает факт с базовой линией,
формирует единый прогноз оставшегося времени и бюджетных корректировок. При
существенном отклонении руководитель проекта создает сценарий, оценивает последствия
и после согласования вводит новую версию плана.

```mermaid
sequenceDiagram
  participant TT as Task Tracker
  participant PS as Planning System
  participant NS as Notification Service
  actor PM as Руководитель проекта

  PS-->>TT: Проекты, структура, сроки и назначения
  TT-->>PS: TaskCreated / TaskChanged / TimeLogged
  PS->>PS: План-факт и единый прогноз остатка
  PS-->>NS: Запрос оповещения об изменении или отклонении
  NS-->>PM: Оповещение
  PM->>PS: Создать и сравнить сценарии
  PS-->>PM: Влияние на сроки, ресурсы и бюджетную корректировку
  PM->>PS: Утвердить новую версию
  PS-->>TT: Обновленные плановые рамки
```

## 5. Критерий готовности

Пользователь может создать проекты, сформировать годовой план, перейти к скользящему
планированию, распределить людей, увидеть Гант и конфликты, сравнить сценарии,
утвердить версию, опубликовать проекты в Task Tracker и получить обратно факт для
единого прогноза. Keycloak, справочники, вложения и оповещения работают в составе
первой версии.

## 6. Архитектурные принципы и границы

- Planning System является мастер-системой проектов и плановых версий; Task Tracker
  является мастер-системой задач и факта их исполнения.
- Keycloak используется как готовый компонент аутентификации; отдельный сервис входа
  не создается.
- Интеграции с Keycloak, Reference Manager, Task Tracker, Notification Service и
  Object Storage входят в первую версию.
- Утвержденная версия плана неизменна; обмен выполняется через версионированные API
  и идемпотентные события.

### 6.1. C4 Context

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

### 6.2. C4 Containers

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

### 6.3. Компоненты Planning Core

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

### 6.4. UML: концептуальная модель

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

## 7. Интеграции и владение данными

| Данные | Мастер-система | Правило обмена |
|---|---|---|
| Проект, декомпозиция, версия плана, сценарий, назначение | Planning System | публикуются в Task Tracker |
| Задача, статус, история, комментарий, фактические часы | Task Tracker | передаются в Planning System через API и события |
| Пользователь, пароль, сессия, группа | Keycloak | аутентификация по OIDC |
| Роль, грейд, календарь и классификатор | Reference Manager | чтение по стабильным кодам |
| Файл вложения | Object Storage | Planning System хранит связь и метаданные |

После публикации проекта Task Tracker хранит его внешний идентификатор из Planning
System. Проекты не импортируются из Task Tracker; обмен задачами через файлы не
предусмотрен. Planning System отправляет запросы оповещений в Notification Service
и плановые проекции в Reporting.

Исходящие события: `ProjectCreated`, `ProjectChanged`, `PlanActivated`,
`AllocationChanged`, `RemainingForecastChanged`, `BudgetAdjustmentChanged`,
`NotificationRequested`. Входящие: `TaskCreated`, `TaskChanged`, `TaskCommented`,
`TimeLogged`, `NotificationDelivered`, `ReferenceItemChanged`. Каждое событие
содержит `eventId`, `eventType`, `occurredAt`, `producer`, `schemaVersion`,
`correlationId` и идентификатор проекта Planning System.

## 8. Развертывание

Planning System использует общую инфраструктуру проекта: Keycloak, PostgreSQL,
брокер сообщений, Object Storage, централизованные журналы, метрики и трассировку.
Секреты задаются средствами среды развертывания и не хранятся в репозитории.
