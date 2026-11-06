# Реестр межкомандного принятия

Обновлено 07.11.2026 по [замечаниям PR #154](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/pull/154).
База сверки: main `1a346249a166ee9a13a87c5476d19d73b3bb624b`.
Запросы #142, #143, #145, #146, #147 опубликованы 18.10.2026 пользователем
pachecou; обсуждения повторно прочитаны 07.11.2026. Учтены ответы Reports от 25/29.10
и Reference Manager от 04.11; в #142/#145/#146 ответов второй стороны нет. Запрос и ответ не равны
приёмке интеграции. Реальные credentials передаются вне GitHub.

| Связь / вопрос | Запрос / дата | Подтверждённое состояние на 07.11 | Статус / условие закрытия |
| --- | --- | --- | --- |
| INT-01, Infra access | [#142](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/142), 18.10 | PR #128 уже влит в main; ответа о выдаче клиентов/JWKS/audience нет | pending: параметры и общий вход T-INT-01 |
| INT-02, D-02/03 | [#143](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/143), 18.10 | pErfEcto2 / RM ответил 04.11: numeric id, revision/is_deleted, pageToken, rename, employment/account state, demo fixture и planning-service; календарь/нормы ведёт PS | agreed по контракту: следующий шаг PS — HR-чтение и T-INT-02 на стенде RM; общий клиент Infra ещё не выдан |
| INT-03, D-01/07 | [#145](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/145), 18.10 | Mapping PUT/facts/events предложен; ответ TT отсутствует | pending: подпись mapping и T-INT-03 |
| INT-04, D-04 | Решение PS от 29.10: вопрос владельцу общего проекта; отдельное обращение не отправлено | Поставщик уведомлений не назначен, у Reports тот же Q-REP-13 | pending: назначение поставщика и принятие схем/receipt |
| INT-05/08, D-05 | [#147](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/147), 18.10 | DarkMast001 / Reports принял 25.10 schemaVersion 1.0.0 / TTL 24 ч / 02:00 Europe/Moscow; 29.10 приняты все четыре уточнения PS | agreed по контракту: общий T-INT-08, клиент S-06 и CronJob Infra ещё открыты |
| INT-06, S3 | [#142](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/142), 18.10 | Infra уже содержит arch-dev-planning-system; выдача credentials/ACL и smoke не подтверждены | pending: выдача и T-INT-06 |
| INT-07, D-09 | [#146](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/146), 18.10 | release-context 1.1.0 реализован и покрыт API-тестами PS; ответа QA нет | pending: источник итераций, принятие QA и T-INT-07 |

Контрольная дата 02.11.2026 прошла; опубликованного протокола общего T-INT-08
в #147 на 07.11 нет. Новый слот назначается после выдачи S-06 и адреса стенда,
а T-INT-02 — после запуска HR-reader против стенда RM. Остальные владельцы
фиксируют ответ или причину задержки в существующих задачах. Новая дата без
согласия второй стороны не назначается. Существующие обращения не дублируются;
контракт agreed не переводится в tested без фактического прогона.

## Task Tracker D-01

Сверка с [TT 130](../../task-tracker/docs/block-g-api-and-events/130.api-contracts.md)
и [его OpenAPI](../../task-tracker/docs/block-g-api-and-events/openapi.yaml).
Наш task-tracker-receiver.openapi.json сохраняется как прежнее предложение;
он не объявляется API владельца. [worker](../server/worker.py) содержит кандидат
адаптера, отправка реальному TT запрещена до TT_MAPPING_APPROVED=true после ответа.

| PS | Контракт TT | Решение / открытый пункт |
| --- | --- | --- |
| projectId UUID | externalId в PUT /api/v1/planning/projects/{externalId} | Использовать UUID строкой, не содержит двоеточий; подтвердить |
| /versions/{planVersionId} в старом предложении | Один PUT пути проекта, версия в body.version | Adapter, не отправлять старый payload напрямую |
| versionNumber / planVersionId | PlanInput.version integer, PlanResult.version | Версию сравнивать по versionNumber; хранить UUID и receipt локально |
| name | title | Явное переименование на wire |
| start/finish | startDate/dueDate | ISO date, не UTC timestamp |
| EPIC/FEATURE logicalItemId | epics[].externalId / tasks[].externalId | EPIC → epic; FEATURE → planned TASK — кандидат, требует согласия о владении |
| Allocation.employeeId = employees/... | assigneeId | Не передавать HR resource name как Keycloak sub; определить account_user_id и несколько назначений |
| Статус применения APPLIED | status applied/already-applied/retired/already-retired | applied/already-applied → receipt; retired не означает активацию |
| sourceRevision / absolute actualHours | facts WorkItem.version / actualHours | Проверить монотонность версии факта и событие TimeLogged |
| remainingHours = согласованный ETC | remainingHours может быть отрицательным арифметическим остатком | Хранить в sourceRemainingHours; ETC не выводить автоматически |
| isDeleted/tombstone | Отсутствие задачи в следующем plan не удаляет её | Нужен явный протокол удаления/сверки |
| snapshot/cursor PS | facts page/pageSize <=500 | Страницы TT не общий snapshot; нужны watermark/повторная сверка |
| Task* envelope PS | task-tracker.events.v1, aggregateId/eventId | Сопоставить фактические eventType/payload/версии; не объявлять совместимость автоматически |

Пути PUT /planning/projects/{externalId}, facts и /reports/iterations выше
взяты из документированного предложения TT. В runtime текущей ветки main
обработчиков приёма плана и facts в backend нет; спецификация не доказывает их реализацию. До ответа #145 и проверки
реального обработчика нельзя включать adapter, объявлять чтение итераций
работающим или выдавать mock receipt за квитанцию TT. Источник итераций и
привязка к RELEASE согласуются с QA. Датированное принятие mapping и успешный
T-INT-03 являются отдельными условиями.

## Reference Manager D-02/D-03

Основание — [ответ pErfEcto2 от 04.11.2026](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/143#issuecomment-6632199921),
[RM 130](../../reference-manager/documents/130.api-contracts.md), ADR-022.
Приняты поля и правила поставщика, вместо прежнего предложения PS с
resource name/state/etag:

- Коллекции employees, org_units, positions, assignments, salaries, absences,
  project_roles, grades, currencies по `/v1/`; `pageSize` не более 100,
  `pageToken`, `allowDeleted`, `filter`, `order_by`. Ответ содержит массив
  по имени коллекции и необязательный `nextPageToken`.
- Стабильный внешний ключ сотрудника — числовой `id`; `personnel_number` является
  отдельным атрибутом. Изменения определяются по `revision`/`updated_at`,
  удаления — по `is_deleted`; `state`/`etag` отсутствуют. В ответе от 04.11 объявлен переход 1.0.0 → 1.1.0;
  в текущем main уже есть readTime 1.1.0. Клиент PS использует его для единого среза.
- Rename сохраняет `id`, `username` и `account_user_id`. Увольнение означает
  `employment_state=DISMISSED`, `account_state=DISABLED` и закрытие периодов,
  а не удаление. Для новых назначений нужен неудалённый EMPLOYED сотрудник;
  отключённая учётная запись не становится допустимым назначением автоматически.
- Календарь, нормы и почасовые ставки ведёт PS. Месячный оклад не пересчитывается
  без принятой методики D-07. Событий RM нет: повторное чтение не реже раза в час.
  Даты — YYYY-MM-DD, timestamps — RFC 3339 UTC.
- Fixture RM — [demo.sql](../../reference-manager/deployments/seed/demo.sql),
  сотрудники 1…8 и связанные справочники. Локальный адрес стенда модуля —
  `http://localhost:8083/v1/`, клиент `planning-service`, роль
  `reference-hr-reader`; секрет передаётся вне Git. На общем стенде клиента
  выдаёт Infra, запрос RM [#163](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/163).

Следующий T-INT-02 ведёт PS: прочитать все страницы, сопоставить HR id и
account_user_id, повторить rename/увольнение/удаление и недоступность источника,
проверить запрет новых назначений и сохранность утверждённого baseline.
Контрактный ответ RM закрывает вопрос о формате, но запуск на модульном и общем
стендах ещё требует самостоятельного протокола. Внесение текущего кэша не должно
переписывать employee IDs и значения в исторических планах.

## QA D-09

Попросить принять PS getReleaseContext версии 1.1.0 с qa.read:
без planVersionId возвращается активный план, явный ID выбирает историческую
утверждённую версию. Оба варианта проверены серверными тестами. Принять контракт с
логическим ID релиза, APPROVED/ACTIVE/историческими версиями, null/PARTIAL
итераций. Зафиксировать один источник итераций: прямой TT или подтверждённая
проекция PS. Новое замечание «нет ссылки на контракт у QA» уже не актуально:
[QA 160](../../qa/docs/160.integration-plan.md) содержит I-03 и Q-03/Q-04.

## Reports D-05

Основание — [ответ DarkMast001 от 25.10.2026](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/147#issuecomment-6395930440).
Reports принял schemaVersion 1.0.0, TTL 24 часа и ежедневную полную партию в
02:00 Europe/Moscow. Владелец расписания — Reports; CronJob Infra и клиент S-06
ещё требуют выдачи/настройки. Внеочередной запуск — не чаще раза в час после
PlanActivated/RemainingForecastChanged/BudgetAdjustmentChanged; пока событий
на общем стенде нет, доступны ежедневный и ручной запуски.

### Ответ Planning System по оставшимся пунктам

PS сформулировал уточнения 29.10.2026; [Reports принял все четыре пункта
в тот же день](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/147#issuecomment-6505753939)
(DarkMast001, база main e4ee17e, потребитель 81417e5). Это датированное
принятие контракта, отдельное от приёмки общего стенда.

1. Партия S-06 — полный срез **экспортируемых данных** указанного портфеля,
   разрешённого portfolio_ids. project_ids токена её не сужает. Черновики и
   версии ON_REVIEW не экспортируются: plan имеет статус ACTIVE/APPROVED/SUPERSEDED.
2. Уточнение вместо прежней фразы «явные ARCHIVED/tombstone»: ARCHIVED-версии
   и данные архивированного проекта (его планы, demand/allocation/forecast)
   отсутствуют в новой партии. Availability остаётся срезом всего портфеля.
   Исчезновение строки из следующей **полностью загруженной READY-партии**
   того же портфеля закрывает запись в DWH с сохранением истории. Это правило
   относится только к batch ETL, не к событиям задач и не к отдельной странице.
3. Результат Idempotency-Key хранится в request_results без автоматического
   удаления, то есть не менее 24 часов. Повтор с тем же subject/operation/key
   возвращает исходную партию; после её EXPIRED нужен новый ключ, повтор не
   продлевает TTL. Чтение существующей партии после 24 ч возвращает BATCH_EXPIRED.
4. Вложенные plan.data.demands/allocations дублируют строки верхнего уровня.
   Reports читает только отдельные entityType demand/allocation, связывает их
   с планом через planItemId/demandId, считает текущими только данные ACTIVE.
   Денежные поля без cost.read отсутствуют, null при наличии права неизвестен.

Формальные уточнения — [130](130.api-contracts.md), [140](140.event-schema.md),
[162](162.integration-spec.md). Регрессия проверяет полный срез нескольких
проектов, неизменяемость старой партии, архивирование и повтор POST/страниц.

T-INT-08 ведёт Reports; PS предоставляет стенд, fixture и S-06. Согласованный
срок до 02.11.2026 прошёл без опубликованного протокола общего прогона в #147.
Для нового слота сохраняются критерии: не менее трёх страниц pageSize=2, counts, повтор POST
и страницы, EXPIRED, два токена с cost.read и без, перепланирование без двойного
учёта. Локальный прогон Reports от 25.10 — доказательство потребителя; текущая
локальная проверка API/ETL не подменяет общий прогон с OIDC и CronJob. Выдача
S-06 и CronJob Infra запрошены Reports в [#158](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/158);
методика стоимости D-07 остаётся открытой.

## Infra

Инфраструктура из [PR #128](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/pull/128)
уже в main. По #142 ожидаются web/API clients, redirect URI, audience/JWKS, отдельные service accounts,
S3 bucket/ACL, broker/topics/DLQ, schedule/TZ, эталонные fixture IDs и адрес/протокол
коллектора. Секреты передаются вне Git; в ответе фиксируются только факт выдачи
и несекретные идентификаторы. Запрос не равен выданным доступам.

В общем realm уже описаны клиенты planning-system/planning-service, но это
не означает готовность claims для PS: требуются бизнес-роли R-01…R-06 и
portfolio_ids/project_ids/employee_ids, сервису Reports — audience PS и
reports.read/reports.export, QA — qa.read. Локальный realm /planning из
compose.oidc.yaml изолирован и не подтверждает общий вход. Root Compose
также не запускает все приложения одной командой; это совместная поставка
Infra и команд модулей.

## Форма ответа и фактической приёмки

Для каждой строки добавить: дата; команда/представитель; ссылка на комментарий/PR;
контракт version/hash; решения по открытым полям; адрес стенда без секрета;
критерии и владелец следующего теста. После ответа pending → agreed, после
реального T-INT с commit/image digest, входами, expected/actual, логами и verdict
→ tested. Отсутствующий сервис = blocked, не passed.
