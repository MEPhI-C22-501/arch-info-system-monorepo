# Состояние доработки Planning System на 18.10.2026

Основание: замечания от 12.10.2026. База main
`f5eb2353e9f6e036730739f9fb8ba269390ae255` влита в рабочую ветку без конфликтов.
Точные входы и SHA-256 — [document-audit.json](../artifacts/document-audit.json),
итоги — [verification.json](../artifacts/verification.json).
Матрица обмена хранится в [020](020.system-context.md).

| Замечание / поставка | Выполненное действие | Граница результата |
| --- | --- | --- |
| Старый PR #21 | PR закрыт; путь А и источник архитектуры записаны в ADR-014; файлы и ссылки README сохранены | Новая ветка проходит отдельное ревью |
| Документ 162 | Восемь связей, альтернативы/плюсы/минусы, выбор, результат, проверки, ссылки на весь комплект | Это проекты межкомандных решений |
| База 095 | Обновлена до main f5eb235; повторены 45 требований и 20 историй; хешируются только исходники, не локальные секреты/БД | 17 covered / 28 partial / 0 missing описывают документы |
| Воспроизводимость | README содержит установку зависимостей и версии Python; CI проверяет push и PR | GitHub-прогон фиксируется отдельно от локального |
| План разработки | Роли, задачи, 194 ч, приоритеты/даты/вехи, критерии и зависимости | Логины участников и дата защиты ещё не предоставлены |
| Архитектура | 150/ADR-016 описывают фактические Python/FastAPI/SQLAlchemy/JavaScript; ADR-013 заменён | HR/Kafka/уведомления и отдельный расчётный worker остаются целевыми |
| API и безопасность | QA без planVersionId читает ACTIVE, явный ID — исторический утверждённый план; 1.1.0 сохраняет совместимость; Bearer, JSON-ошибки и заголовки проверены регрессиями | Доступы и реальный Keycloak ещё требуют общего стенда |
| Контейнер и PostgreSQL | Чистый Compose, миграции/seed, API/worker, 26 тестов на PostgreSQL | Локальные синтетические данные и mock receipts |
| UI и диаграммы | Browser E2E сервера и мобильный вид; 47 Mermaid-диаграмм отрисованы | Общий сценарий с соседями ещё не выполнен |
| Minikube | Deployment/StatefulSet/ConfigMap/Secret/PVC/Service/Ingress; отдельный повторяемый smoke | Локальный dev-кластер, не инфраструктурный staging |
| Восстановление | pg_dump восстановлен в новую БД, проверены snapshots/audit/requests и baseline trigger | RPO/RTO и S3 restore общего стенда ещё открыты |
| Согласования | Подготовлены запросы Infra/RM/TT/QA/Reports; статусы и ссылки — в реестре | Ответы владельцев и реальные T-INT не подменяются локальными тестами |

## Воспроизводимые доказательства

- `python planning-system/scripts/validate-docs.py`: состав, ссылки/якоря,
  таблицы, OpenAPI/HTTP и 35 JSON Schema событий; итоговый счётчик — verification.
- `python planning-system/scripts/audit-traceability.py`: 45 требований,
  20 историй и точные SHA-256 входных файлов.
- `python -m pytest planning-system/tests`: 25 passed / 1 skipped на SQLite;
  PostgreSQL/Python 3.12 — 26 passed, 0 skipped, [XML](../artifacts/postgres-tests.xml).
- `node planning-system/scripts/check-app.mjs`: сохранение на сервере, конфликт,
  согласование/активация, сценарий, возврат, прогноз, файл, XSS, роли и mobile;
  [browser-report.json](../artifacts/browser-report.json) и screenshots в artifacts.
- `node planning-system/scripts/check-prototype.mjs` с Mermaid 11.12.0:
  сценарии прототипа и 47 диаграмм, 0 ошибок.
- `python planning-system/scripts/check-minikube.py --context <dev-context> --restart --ingress`:
  [minikube-report.json](../artifacts/minikube-report.json). Проверяет seed,
  Bound PVC, сохранность проекта и файла после перезапуска PostgreSQL/API,
  сохранность UID PVC и маршрут planning.local через ingress-nginx.
- `python planning-system/scripts/check-restore.py --project <dev-compose>`:
  [restore-report.json](../artifacts/restore-report.json). Исходная БД не заменяется;
  тестовый клон удаляется, worker возвращается в исходное состояние.

Команды подготовки — [development.md](../development.md). Проверки модуля
выполняются только на изолированных синтетических наборах.
[Security report](security-report.md) описывает фактический объём и ограничения.

## Оставшиеся условия общей приёмки

[Реестр согласований](integration-agreements.md) требует датированного ответа
второй команды. D-01…D-09, реальные HR/Kafka/notification adapters, нормы рабочего
календаря, credentials/ACL/коллектор, нагрузочные пороги и общий сценарий
«проект → план → факт → отчёт» пока не приняты. QA уже ссылается на release-context,
но источник итераций не выбран. Reports ещё согласует состав/TTL/расписание партии.
TECH-01/03/06 имеют локальные доказательства; TECH-02 требует успешного CI/выпуска;
TECH-04/05 имеют локальные security/minikube доказательства, но общий стенд
принимается отдельно. Файлы манифестов и локальный passed не закрывают T-INT.
Порядок и владельцы — [160](160.integration-plan.md), [165](165.deployment-diagram.md),
[рабочий план](../work-plan.md), [GitHub](../github-actions.md).
