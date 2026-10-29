# Реестр межкомандного принятия

Обновлено 29.10.2026 по [замечаниям PR #154](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/pull/154).
База сверки: main `338cf0f8eb724992ed29db6a84a7b92f9eeaaae0`.
Запросы #142, #143, #145, #146, #147 опубликованы 18.10.2026 пользователем
pachecou; обсуждения повторно прочитаны 29.10.2026. Запрос и ответ не равны
приёмке интеграции. Реальные credentials передаются вне GitHub.

| Связь / вопрос | Запрос / дата | Подтверждённое состояние на 29.10 | Статус / условие закрытия |
| --- | --- | --- | --- |
| INT-01, Infra access | [#142](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/142), 18.10 | PR #128 уже влит в main; ответа о выдаче клиентов/JWKS/audience нет | pending: параметры и общий вход T-INT-01 |
| INT-02, D-02/03 | [#143](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/143), 18.10 | HR API RM описан; комментариев с принятием rename/норм/fixture нет | pending: ответ RM и T-INT-02 |
| INT-03, D-01/07 | [#145](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/145), 18.10 | Mapping PUT/facts/events предложен; ответ TT отсутствует | pending: подпись mapping и T-INT-03 |
| INT-04, D-04 | Решение PS от 29.10: вопрос владельцу общего проекта; отдельное обращение не отправлено | Поставщик уведомлений не назначен, у Reports тот же Q-REP-13 | pending: назначение поставщика и принятие схем/receipt |
| INT-05/08, D-05 | [#147](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/147), 18.10 | DarkMast001 / Reports ответил 25.10: schemaVersion 1.0.0, TTL 24 ч, 02:00 Europe/Moscow, собственный локальный ETL-прогон | Частично согласовано: ответ PS ниже; T-INT-08 и доступы общего стенда ещё открыты |
| INT-06, S3 | [#142](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/142), 18.10 | Infra уже содержит arch-dev-planning-system; выдача credentials/ACL и smoke не подтверждены | pending: выдача и T-INT-06 |
| INT-07, D-09 | [#146](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/146), 18.10 | release-context 1.1.0 реализован и покрыт API-тестами PS; ответа QA нет | pending: источник итераций, принятие QA и T-INT-07 |

Следующая контрольная точка — 02.11.2026: владельцы adapters PS вместе с
соответствующими командами фиксируют ответы и результаты T-INT либо причину
переноса. Дата является планом PS, не обязательством соседей. Существующие
обращения не дублируются; неподтверждённые строки не переводятся в tested.

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

Итерации TT читаются по /reports/iterations; их version и привязка к RELEASE
согласуются с QA. Без датированного mapping событие адаптера не считается
испытанной интеграцией.

## Reference Manager D-02/D-03

Принять чтение employees/assignments/positions/org_units/absences и классификаторов
по [RM 130](../../reference-manager/documents/130.api-contracts.md), page_token,
state/etag. Ответить: сохраняются ли resource name и account_user_id при rename;
какие состояния запрещают новые назначения; кто подтверждает нормы/TZ.
PS сохраняет прежние значения в baseline, обновляет только текущий кэш. Оклад
не становится почасовой ставкой без методики D-07.

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

Зафиксирован в этой редакции 29.10.2026; публикация PR является предложением
принять уточнения, не подменяет ответ второй стороны.

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

T-INT-08 ведёт Reports; PS предоставляет стенд, fixture и S-06. До 02.11.2026
планируется общий прогон: не менее трёх страниц pageSize=2, counts, повтор POST
и страницы, EXPIRED, два токена с cost.read и без, перепланирование без двойного
учёта. Локальный прогон Reports от 25.10 — доказательство потребителя; новый
общий прогон в этой доработке не объявляется выполненным. Выдача S-06/Infra и
методика стоимости D-07 остаются открытыми.

## Infra

Инфраструктура из [PR #128](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/pull/128)
уже в main. По #142 ожидаются web/API clients, redirect URI, audience/JWKS, отдельные service accounts,
S3 bucket/ACL, broker/topics/DLQ, schedule/TZ, эталонные fixture IDs и адрес/протокол
коллектора. Секреты передаются вне Git; в ответе фиксируются только факт выдачи
и несекретные идентификаторы. Запрос не равен выданным доступам.

## Форма ответа и фактической приёмки

Для каждой строки добавить: дата; команда/представитель; ссылка на комментарий/PR;
контракт version/hash; решения по открытым полям; адрес стенда без секрета;
критерии и владелец следующего теста. После ответа pending → agreed, после
реального T-INT с commit/image digest, входами, expected/actual, логами и verdict
→ tested. Отсутствующий сервис = blocked, не passed.
