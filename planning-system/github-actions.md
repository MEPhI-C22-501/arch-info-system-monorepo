# Публикация и межкомандные действия

Обновлено 07.11.2026 по [PR #154](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/pull/154).
База текущих исправлений — main `1a346249a166ee9a13a87c5476d19d73b3bb624b`.
Локальные изменения, PR, согласование контракта и успешная совместная приёмка
фиксируются отдельными фактами.

## Проверки GitHub

Workflow Planning System checks запускается на push/PR при изменении модуля.
Он проверяет синтаксис, документы/трассировку, воспроизводимость генераторов,
PostgreSQL-тесты, чистый Compose, browser E2E, restore и Mermaid. Отдельное
задание oidc проверяет настоящий локальный Keycloak, JWT и браузерный PKCE.
Публикация образа в GHCR зависит от успешных verify и oidc на main.
Ручной workflow_dispatch с minikube=true добавляет проверку кластера,
Ingress и сохранности PVC. Наличие workflow не подтверждает его последний
успешный запуск; результат GitHub и digest указываются после фактической сборки.

Администратор репозитория определяет обязательность check и права GHCR.
Настройки защиты main не меняются самим наличием workflow. Секреты общего
стенда не передаются в GitHub-артефакты; используются только тестовые credentials.

## Датированные ответы и оставшиеся действия

Запросы опубликованы 18.10.2026: Infra #142, RM #143, TT #145, QA #146,
Reports #147. Обсуждения повторно прочитаны 07.11.2026. Reports принял
версию/TTL/расписание 25.10 и все четыре уточнения PS 29.10. RM ответил 04.11:
numeric id, revision/is_deleted, pageToken, стабильность account_user_id,
fixture и planning-service/reference-hr-reader; календарь и нормы остаются PS.
В #142/#145/#146 ответов второй стороны нет. Точные комментарии и условия
T-INT — в [реестре](docs/integration-agreements.md).

Согласованный срок T-INT-08 до 02.11 прошёл без опубликованного протокола в #147.
Клиент S-06 и CronJob Infra остаются открытыми (#158). Следующий HR-тест за PS,
как прямо указано в ответе RM; это уже не ожидание ответа справочников.
Общий набор, claims/audience, роли и S3 требуют Infra. TT adapter остаётся
отключённым до mapping и действующего приёмника; QA iterations — PARTIAL до D-09.

## Подготовленные обращения

Следующие тексты предназначены для ответов в существующих задачах. В этой
доработке они не публикуются, повторные задачи не создаются. Секреты в них
не включаются. Перед отправкой к запросу прикладываются фактический PR/commit
и результаты, если прогон уже выполнен.

| Адресат / место | Подготовленный текст |
| --- | --- |
| Infra, [#142](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/142) | PR #128 уже в main; просим подтвердить фактическую выдачу PS web/API clients, audience/JWKS и roles/scopes/portfolio_ids/project_ids/employee_ids. Для Reports нужен S-06 с audience PS, reports.read/reports.export и отдельным cost.read; для вложений — bucket/endpoint/ACL. Просим согласовать demo HR/account IDs, адрес общего стенда, порядок выдачи секретов вне GitHub и слот T-INT-01/06; S-06/CronJob также запрошены в #158. |
| Reference Manager, [#143](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/143) | Ответ от 04.11 учтён: принимаем numeric id, revision/is_deleted, pageToken и неизменность account_user_id при rename; нормы и календарь ведём у себя, месячный оклад не считаем почасовой ставкой. Следующий тест ведёт PS с planning-service/reference-hr-reader: страницы, rename/увольнение, fixture 1…8 и сохранение baseline. Просим подтвердить доступность модульного стенда и способ получения секрета вне GitHub. |
| Task Tracker, [#145](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/145) | Просим принять mapping проекта/планового эпика PS и задач/факта TT или предложить корректировку; указать реально реализованные пути приёма плана, receipt и сверки факта. Документированные PUT/facts/iterations не подтверждены как действующий runtime текущего main. Нужны версии/sourceRevision, retirement/tombstone, account_user_id и несколько назначений. До принятия и T-INT-03 TT_MAPPING_APPROVED остаётся false. |
| QA, [#146](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/146) | Просим принять release-context 1.1.0, scopes и историческую привязку planVersionId/logicalItemId; выбрать источник итераций (TT напрямую или проекция PS). Без принятого источника iterations=null/PARTIAL. Нужны fixture тест-плана, сервисный клиент и слот T-INT-07; DRAFT и чужая область должны отклоняться. |
| Reports, [#147](https://github.com/MEPhI-C22-501/arch-info-system-monorepo/issues/147) | Ответы от 25/29.10 учтены, все четыре уточнения согласованы. Общий T-INT-08 до 02.11 не подтверждён опубликованным протоколом. Просим после выдачи S-06/CronJob (#158) согласовать новый слот; PS предоставляет адрес стенда и portfolioId fixture. Сохраняем counts, три страницы pageSize=2, повтор POST/страницы, EXPIRED, cost.read и перепланирование; общий результат фиксируется с commit/image digest. |
| Руководитель проекта / назначаемый владелец уведомлений | Просим назначить поставщика уведомлений для INT-04/D-04 и Reports Q-REP-13, выбрать каналы, версии запросов/receipt, timeout/retry/DLQ и ответственного за T-INT-04. Без владельца и действующего сервиса результат остаётся pending. Отдельная задача и адресат пока не определены. |

Логины участников для назначения задач из [рабочего плана](work-plan.md) и дата
защиты ещё ожидаются. Исполнители/reviewers не назначаются вымышленными именами.
Общий сценарий с соседями, security/restore и T-INT требуют собственных
протоколов по 095/160/165; локальные smoke и прежние artifacts их не заменяют.
