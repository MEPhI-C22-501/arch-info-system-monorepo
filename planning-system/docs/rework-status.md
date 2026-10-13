# Состояние доработки Planning System на 13.10.2026

Основание: замечания от 12.10.2026. Повторная база main
`27864b5e707a77b922cb4fb7db5df68be4271fe3`; точные входы текущей ветки и SHA-256 —
[document-audit.json](../artifacts/document-audit.json). Матрица обмена — [020](020.system-context.md).

| Область | Исправлено / поставлено | Граница результата |
| --- | --- | --- |
| Устаревший PR #21 | Путь А записан в ADR-014; файлы-основания и README-ссылки сохранены; UML в генераторе 120; HR rename в 020 | Старый PR закрывает человек после принятия новой ветки |
| 095 и 162 | Актуальная база/трассировка; 8 отдельных связей с плюсами/минусами, ожидаемым результатом и критериями; ссылки 130/135/140/145/160/165 | D-01…D-09 не объявлены принятыми |
| Воспроизводимость | Команды pip/validator и Python 3.14.3 в README; CI/контейнер Python 3.12 | Проверка документации не подменяет runtime-приёмку |
| План разработки | Задачи, роли, оценки 194 ч, приоритеты/даты/вехи и двусторонние зависимости | Реальные логины и даты принимает руководитель команды |
| Сервер и БД | 26 основных API-операций, ресурсные/UI-маршруты, PostgreSQL JSONB snapshots, optimistic revision, idempotency, migration/DB guard | Нормализация 24 таблиц пока целевая, фактическая схема — ADR-015/120 |
| UI | 12 экранов по прототипу с серверными запросами; проекты/структура/ресурсы/согласование/файлы/прогноз | Развитие редакторов сложных календарей/интеграций остаётся следующей итерацией |
| Compose и seed | API, worker, PostgreSQL и миграция/идемпотентный synthetic seed; проверен чистый запуск | Общий стенд и minikube smoke ещё требуют приёмки |
| Контракты соседей | TT mapping сравнен; QA уже ссылается на release-context; запросы подготовлены | Реальных ответов/credentials/сквозных T-INT нет |
| Технические проверки | API/domain/JWT/PG trigger, browser test и security report | Полные NFR, backup/restore, реальные Kafka/DLQ и telemetry не закрыты |

## Воспроизводимые результаты

- `python planning-system/scripts/validate-docs.py`: ссылки/якоря, состав 24 позиций,
  45 требований, 20 историй, 35 event schemas и HTTP/OpenAPI. Итоговый счётчик —
  [verification.json](../artifacts/verification.json).
- `python planning-system/scripts/audit-traceability.py`: 45 требований,
  17 covered / 28 partial / 0 missing по полноте документов, все 20 историй
  трассированы; hash каждого входа. Статусы не обозначают passed приложения.
- `python -m pytest planning-system/tests`: локальный Python 3.14.3/SQLite —
  19 passed, 1 skipped (PostgreSQL trigger); контейнерный Python 3.12/PostgreSQL —
  полный набор без SQLite-пропуска, результаты в postgres-tests.xml.
- Чистый Docker Compose: postgres healthy, migration/seed exit 0, API ready,
  worker запущен; сборка image и состояние отражены в verification.json.
- `node planning-system/scripts/check-app.mjs`: реальный серверный цикл и
  скриншоты, итог — browser-report.json. Mock delivery помечена mock:.
- minikube YAML и Secret template поставлены; реальный minikube smoke и GitHub
  CI/выпуск выполняются после публикации/подготовки среды, пока не passed.

## Оставшиеся ручные и межкомандные действия

[GitHub](../github-actions.md): создать PR, закрыть #21, назначить исполнителей,
включить обязательный CI/права GHCR, проверить Mermaid на GitHub и отправить
[запросы соседям](integration-agreements.md). Секреты передаются вне Git.

TECH-01/03/06 имеют локальные доказательства для поставленного объёма;
TECH-02 — workflow поставлен, GitHub-прогон ещё ожидается;
TECH-04 — локальный отчёт, полный checklist/реальный стенд остаётся;
TECH-05 — манифесты, фактический minikube/PVC smoke остаётся.
T-INT-* остаются planned/blocked до датированных соглашений и реальных сервисов.
Сквозной сценарий «проект → план → факт → отчёт» с соседями, централизованная
телеметрия, уведомления, Kafka mapping/DLQ, нормы рабочего календаря и нагрузочные
пороги не объявлены завершёнными. План и критерии — [160](160.integration-plan.md),
[165](165.deployment-diagram.md), [рабочий план](../work-plan.md).
