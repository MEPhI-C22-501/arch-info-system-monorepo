# Реестр межкомандного принятия

13.10.2026. База сверки main 27864b5. Описанный контракт и письменное принятие
версии — разные доказательства. Запросы ниже подготовлены, но не отправлены;
отправка на GitHub — [ручные действия](../github-actions.md). В ответе нужны
дата, представитель второй команды, версия/hash, выбранный вариант и ссылка.

| Связь / вопрос | Текущее доказательство | Ответ второй стороны с датой | Статус |
| --- | --- | --- | --- |
| INT-01, Infra access | Infra vision, набор среды в PR #128 | Нет ссылки на выдачу client/JWKS/audience | pending |
| INT-02, D-02/03 | HR-мастер заявлен обеими командами; контракт чтения RM 130 | Нет принятия rename/норм и fixture smoke | pending |
| INT-03, D-01/07 | TT 130 и OpenAPI теперь имеют PUT/facts; форматы различаются | Нет двустороннего mapping/версии | pending |
| INT-04, D-04 | Асинхронные схемы PS 135/140 | Поставщик и receipt не приняты | pending |
| INT-05/08, D-05 | Reports 160 описывает projection/партии и Q-REP-05 | Нет принятия полей/TTL/расписания | pending |
| INT-06, S3 | Infra называет arch-dev-planning-system | Нет выдачи credentials/ACL и smoke | pending |
| INT-07, D-09 | QA 130/160 от 12.10 уже ссылается на release-context, Q-10 закрыт | Q-03/Q-04 остаются; источник итераций не выбран | pending |

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

Попросить принять точную версию PS getReleaseContext с planVersionId и qa.read,
логическим ID релиза, APPROVED/ACTIVE/историческими версиями, null/PARTIAL
итераций. Зафиксировать один источник итераций: прямой TT или подтверждённая
проекция PS. Новое замечание «нет ссылки на контракт у QA» уже не актуально:
[QA 160](../../qa/docs/160.integration-plan.md) содержит I-03 и Q-03/Q-04.

## Reports D-05

Попросить согласовать plan/demand/availability/allocation/forecast, manifest counts,
schemaVersion, ARCHIVED/tombstone, cost.read, срок batch (локально 24 ч),
расписание/TZ, checkpoint batchId и staging merge. Предложение начального
расписания: ежедневно 02:00 Europe/Moscow + ручной повтор; принять или изменить
в ответе. Повтор строки ключуется (batchId, entityType, entityId), EXPIRED начинает
новый batch; частичный staging не становится витриной.

## Infra

Попросить решение по [PR #128](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/pull/128),
web/API clients, redirect URI, audience/JWKS, отдельные service accounts,
S3 bucket/ACL, broker/topics/DLQ, schedule/TZ, эталонные fixture IDs и адрес/протокол
коллектора. Секреты передаются вне Git; в ответе фиксируются только факт выдачи
и несекретные идентификаторы. Запрос не равен выданным доступам.

## Форма ответа и фактической приёмки

Для каждой строки добавить: дата; команда/представитель; ссылка на комментарий/PR;
контракт version/hash; решения по открытым полям; адрес стенда без секрета;
критерии и владелец следующего теста. После ответа pending → agreed, после
реального T-INT с commit/image digest, входами, expected/actual, логами и verdict
→ tested. Отсутствующий сервис = blocked, не passed.
