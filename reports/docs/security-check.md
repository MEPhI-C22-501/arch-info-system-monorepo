# Проверка безопасности Reports

Исполняемый объём — [R-01…R-11/API/UI/файлы/подписки/аудит](product-implementation.md).
Проверки относятся к локальному стенду с синтетическими данными; права реальных
источников, общий Keycloak/proxy, эксплуатационные копии и MinIO принимаются отдельно.

| ID | Локальный результат | Доказательство / остаток |
| --- | --- | --- |
| S-01 XSS UI | DOM textContent, без innerHTML/eval; CSP, экранированная печать | test_product.py, product_ui.py, браузерный R-06; полного pentest нет |
| S-02 XSS Superset | HTML_SANITIZATION и ESCAPE_MARKDOWN_HTML включены | check_session.py; R-01 показывает проверенные идентификаторы, отдельный браузерный payload-тест Superset не заявляется |
| S-03 CSV injection | Опасные префиксы после пробелов/BOM экранируются; XLSX inline strings, без формул и ссылок | XML ZIP разбирается тестом; опасные строки остаются текстом |
| S-04 CSRF/CORS | Reports API только Bearer, cookie не авторизует; CORS не разрешён. Superset отклоняет чужой Origin даже с действующим CSRF | test_http_boundary.py, check_bi.py, check_session.py |
| S-05 SQL injection | Связанные параметры, закрытый список фильтров/разрезов; имена таблиц/порядок сортировки внутренние константы | test_pipeline.py, test_product.py; пользовательский SQL не принимается |
| S-06 Scope | Member self; PM/TL/QA только выданные scopes; analyst all; admin-only без бизнес-данных | HTTP /pilot также убирает старый admin shortcut, Cube global — analyst, Superset Admin только admin+analyst |
| S-07 Чужой файл | 404, TTL 24 ч/410; текущие права и fingerprint, SHA-256; без публичных URL и пользовательских путей | native/HTTP/живые проверки; общий MinIO отдельно |
| S-08 JWT | RS256/JWKS, iss/aud/exp; UI Authorization Code + PKCE S256, state; токен только в памяти | Настоящие Keycloak, API, Cube, Superset; истечение/ротация проверены; мгновенный logout отдельно |
| S-09 Секреты | Только ~/secrets.env; редактирование вывода и скан исходников/артефактов/логов | check_secrets.py: известные raw/URL/JSON значения, JWT и private key; неизвестный формат не гарантируется |
| S-10 Права | Источники только читаются; POST только создание партии Planning. API Reports — отдельный reports_app | Реальные роли источников отдельно; локальному worker нужен admin read realm, общему — read-only service account |
| S-11 События | Проектные схемы не несут значений показателей или персональных имён | Проверка схем; Kafka publisher полного продукта пока не включён |
| S-12 Аудит | INSERT-only события, хеш запроса, actor/action/report/resource/result/time/correlation | PostgreSQL блокирует UPDATE/DELETE/TRUNCATE, приложение не владелец; SQLite также проверен |

## Проверки жизненного цикла

- Перед каждой доставкой worker читает текущие enabled/роли из локального Keycloak.
  Для каждого получателя отдельный файл в пересечении его области и области владельца.
  Отзыв роли синтетического member2 проверяется живым тестом и восстанавливается в finally.
- Потерявший право владелец приостанавливает подписку. Отказ каталога доступа
  не превращается в разрешение; в журнале доставки фиксируется пропуск.
- Скачивание повторно проверяет получателя. Изменение role/scope/mapping
  не позволяет скачать файл, сформированный в более широкой области.
- Версия If-Match защищает обновления подписки. Завершение терминально.
  PostgreSQL advisory lock и уникальный delivery key предотвращают дубли.
- Ошибка формирования не оставляет частичный файл и не блокирует следующие задания.
- Отсутствующий срок, ставка, история, категория WORKING или связь ID
  не подменяются вымышленным нулём. Q-REP-12 не считается утверждённой методикой.
- Аудит не хранит токены, пароли, сырые query payload или ответы.
  События успешных API-операций фиксируются до ответа; при отказе аудита операция
  не выдаётся как успешная. Во время недоступности БД сохранение события не гарантируется.

## Протоколы

[Общий прогон](../pilots/artifacts/verification.json),
[продуктовый стенд](../pilots/artifacts/product-verification.json),
[BI](../pilots/artifacts/bi-verification.json),
[ротация и роли](../pilots/artifacts/role-verification.json),
[восстановление PostgreSQL](../pilots/artifacts/restore-verification.json),
[скан секретов](../pilots/artifacts/secret-verification.json).

Сеанс Superset ограничен проверенным exp; активный JWT может оставаться действующим
до exp. Это не обещание мгновенного back-channel отзыва. Протокол pg_dump/restore
относится к локальной синтетической БД, не к копии общего Keycloak и не к RPO/RTO
развёрнутой системы. При скачках часов Colima ранее наблюдался SystemTimeError
Cube; успешный прогон не доказывает устранение причины внутри Cube.
