# Реестр замечаний

Источник ревью — `infra0to-do.md` от 01.10.2026. Утверждения сверены с репозиторием 06.10.2026. Устаревшие пункты не повторяются как открытые дефекты.

| Замечание | Задача | Артефакт | Проверка | Статус |
| --- | --- | --- | --- | --- |
| Нет комплекта документов | Шаг 0–5 | `infra/docs/` | `check-mermaid.py`, `validate-contracts.py` 06.10.2026 | verified |
| Пустой Compose | Шаг 2 | `compose.yaml`, `compose.dev.yaml` | `docker compose config` и `infra/scripts/smoke.sh` exit 0 | verified |
| Нет realm и клиентов | Шаг 2 | `infra/keycloak/realm/desired.json` | Bootstrap повторно, токен `example-caller` после restart | verified |
| Нет MinIO | Шаг 2 | `infra/images/minio` | Сборка, digest `sha256:cc5db89840c1112b7b9f7bd1a765be04f48087d5bbf8c2f06ba9d064b6f7560f`, бакеты и эталон S3 | verified |
| Нет эталонов | Шаг 3 | `infra/examples/` | `run-examples.sh`: успех, отказ, повтор, DLQ, OIDC, span коллектора | verified |
| CI отключён | Шаг 7 | `.github/workflows/` | Файлы workflow разобраны; прогон GitHub Actions не выполнялся | implemented |
| Нет seed | Шаг 4 | `infra/seed/reports-mart.sql` | Повторный seed вставил 0 строк; после restart `demo_link` содержит 5 строк | verified |
| Нет коллектора | Шаг 2 | `infra/config/otel/collector.yaml` | В `signals.json` найден span `infra-smoke` | verified |
| Нет реплики Reports | Шаг 4 | `reports-db` и `reports-db-replica` | `CREATE TABLE` на реплике отклонён, lag 0,26 с, restore drill вернул 5 строк | verified |
| Нет DLQ-контракта | Шаг 1 и 3 | `140`, эталон Kafka | Эталон прошёл исчерпание и восстановление; бизнес-топики не agreed | verified для эталона, draft для команд |
| Нет minikube | Шаг 6 | `infra/k8s/` | `minikube` и `kubectl` не установлены, кластер не запускался | blocked для запуска, манифесты есть |
| Справочники запрещают учётные записи | Не повторять | vision справочников от 02.10.2026 уже включает HR и Keycloak | Сверка `reference-manager/documents/vision.md` | устарело |
| Битая ссылка на vision справочников | Шаг 0 | `infra/vision.md` | Путь `reference-manager/documents/vision.md` существует | verified |
| Пять видов интеграции | Шаг 0 | vision, 162, 078 | В перечне четыре вида, `check-mermaid.py` успешен | verified |
| QA нет в границах и бакетах | Шаг 0 и 2 | vision, бакет `arch-dev-qa` | Бакет создан, политика `qa-own` привязана к `qa-system` | verified |
| События Task Tracker и Planning не совпадают | Шаг 1 | `135`, `160` | Расхождение зафиксировано, контракт не объявлен agreed | draft |
| QA отказывается от DLQ | Шаг 1 | `135`, ADR-011 | Повтор издателя и DLQ потребителя разделены | draft |
| Общий OpenAPI справочников отсутствует | Шаг 1 | `130`, `catalog.yaml` | Файла `api/openapi/v1/openapi.yaml` нет | draft, задача команды |
| Q-REP-01 | Шаг 4 | ADR-012, реплика своей витрины | Реплика своей базы запущена; толкование постановки Reports не подтверждено | proposed, реплика verified в Compose |
| Площадка, TLS, реестр | Шаг 7 | runbook release | Внешний deploy не настраивался | blocked |
| Готовые серверы Planning, Reports, QA | Шаг 4 | `compose.modules.yaml` | В репозитории нет серверной поставки | blocked |

Проверки выше выполнены локально 06.10.2026. `verified` относится только к названной команде. Согласие команд, внешний стенд и minikube из этого не следуют.
