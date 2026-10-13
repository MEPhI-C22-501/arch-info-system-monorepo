# Фактическая локальная проверка безопасности

13.10.2026. Область: модуль Planning System текущей рабочей ветки на базе
main 27864b5, синтетический stand/тестовая БД. Это локальная регрессия, не полный
пентест общего стенда. Версии входов фиксирует document-audit.json; результаты
серверного прогона — [postgres-tests.xml](../artifacts/postgres-tests.xml),
браузерные проверки — [browser-report.json](../artifacts/browser-report.json).
Данные пользователей/секреты соседей не использовались.

| Кейс | Фактическая проверка | Результат / доказательство | Ограничение |
| --- | --- | --- | --- |
| XSS | Имя проекта со script сохраняется, вывод экранирован; browser window.xss не появляется | Автотест test_attachments_security_origin_and_no_injection и check-app.mjs | Все точки вывода и HTTP на общем ingress ещё требуют отдельного сканирования |
| CSRF/origin | PATCH с Origin attacker.invalid отклонён 403, объект не меняется | Серверный security-кейс | Cookie auth не используется; Keycloak redirect/PKCE на реальном сервере ещё не испытан |
| SQL injection | SQL-подобная строка в имени/goal/фильтре хранится/ищется как значение | Параметризованный SQLAlchemy, выборка не расширилась | Нагрузочный и полный fuzzing не выполнялся |
| JWT | Проверены RS256-подпись, issuer, audience, exp; неверный ключ и изменённые claims отклонены | test_oidc_signature_issuer_audience_expiry | JWKS заменён тестовым ключом; реальная ротация Keycloak остаётся T-INT-01 |
| RBAC/IDOR | R-05/R-06/сервисы не читают полный план; чужой ID 404, admin activation 403 | Параметризованные tests ролей и foreign_scope | Нужен реальный realm mapping и полный перебор матрицы 070 |
| Upload | Реальная TXT-загрузка/чтение; ровно 20 MiB приняты, +1 байт отклонён; поддельный PDF MIME отклонён 422; admin не читает | test_attachments_security_origin_and_no_injection | Полный набор MIME/вредоносных файлов и антивирус не испытывались |
| Baseline | Изменение APPROVED/ACTIVE запрещено API; PostgreSQL-триггер запрещает прямой UPDATE | test_postgres_baseline_trigger | Привилегии DB/service account общего стенда принимает Infra |
| Replay | Повтор команды/event не дублирует бизнес-эффект; конфликт payload отклонён | idempotency/event tests | Реальная Kafka/DLQ и окно replay ещё не приняты |
| Restore / RPO/RTO | Протокол подготовлен в 165 | planned | Фактический restore/бэкапы общего стенда не выполнены |

Локальные исправления: обязательный If-Match при удалении вложения; повтор команды
повторно проверяет права/область; signed cursor связан с фильтрами и scope;
изменение ресурсных входов отменяет черновое согласование, активация сверяет snapshot;
CSP/nosniff/no-store и файлы с Content-Disposition attachment. Demo auth и local
storage запрещены вне development. В Git нет выданных runtime-секретов.

Открытые действия TECH-04: реальные Keycloak/S3/JWKS/Ingress; полный чек-лист 165,
включая масштабный IDOR-перебор, scanner, restore и повтор после
обнаруженных дефектов. Результат каждого — commit/image digest, среда, expected/
actual, логи, passed/failed/blocked. Отсутствующий сервис не переводится в passed.
