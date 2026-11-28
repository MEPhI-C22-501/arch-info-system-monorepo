# Сценарии качества Reports

> Требования — [075 NFR](075.nfr.md); конвейер и свежесть — [конвейер ETL](etl-pipeline.md). Каждый сценарий
> подтверждён проверкой: тест в `pilots/tests/` или прогон из `pilots/`, все запускаются командой
> `python reports/ci/run_checks.py` (кроме живых прогонов против стендов соседей — их команды указаны).

Сценарий записан как «стимул → ожидаемая реакция → измеримый признак». Общее правило для всех отказов:
загрузка источника принимается целиком или не принимается совсем, прежние данные остаются в отчётах,
а отчёт помечает их как устаревшие.

| № | Стимул | Ожидаемая реакция | Измеримый признак | Проверка |
| --- | --- | --- | --- | --- |
| QS-01 | Источник недоступен: таймаут, отказ соединения, ответ 5xx | Пакет `REJECTED`, checkpoint не сдвигается; отчёты отдают прежние данные; следующий такт повторяет загрузку; после успешной загрузки — снова актуально | В ответе отчёта `freshness.state = STALE`, лаг растёт; `GET /readyz` — 503; после восстановления `FRESH` и 200 | `test_worker.py`: `test_source_failure_preserves_data_but_marks_it_stale_then_recovers`, `test_failures_are_retried_without_logging_dependency_secrets` |
| QS-02 | Источник отказывает в доступе: служебному входу Reports не выдана роль (401, 403) | Пакет `REJECTED`; причина словами — какой роли не хватает и кто её выдаёт; пока источник не загружен ни разу, Reports не готов | `reason` в журнале пакетов (`GET /api/v1/etl/batches`, экран «Актуальность») и в журнале ETL; `GET /readyz` — 503 с `sources.<источник>.lastRejection` | `test_product.py`: `test_readiness_needs_every_source_and_explains_a_403`; `ui/src/test/etl.test.tsx` |
| QS-03 | Неполные данные: пропала страница, изменилось общее число строк при обходе, повтор записи на разных страницах, запись не по контракту | Пакет отклоняется целиком, частичная загрузка не применяется; прежние факты и checkpoint не меняются | `etl.batch.status = REJECTED`, код `INCOMPLETE_PAGE`, `COUNT_MISMATCH`, `UNSTABLE_PAGES`, `DUPLICATE_ID` или `TRACKER_CONTRACT_VIOLATION`; сумма часов в R-01 прежняя | `test_pipeline.py`: `test_missing_middle_page_rejected`, `test_changing_total_rejected`, `test_repeated_record_across_pages_rejected`, `test_tracker_missing_required_field_rejected`, `test_rejected_batch_keeps_previous_checkpoint_and_facts`; `test_acceptance.py`: `test_bad_pages_of_each_catalog_preserve_checkpoint_and_previous_records` |
| QS-04 | Слишком старый срез: партия Planning старше уже загруженной, срез справочника без часового пояса или старше текущей истории | Срез не применяется, история и факты не откатываются назад | Код `OUT_OF_ORDER_BATCH` (повтор слота — `SKIPPED`, `SUPERSEDED_BATCH`); версии измерений прежние | `test_history.py`: `test_stale_or_timezone_free_batch_cannot_replace_current_history`; `test_pipeline.py`: `test_expired_unsupported_and_bad_count_batches_rejected`, `test_planning_permission_or_expiry_change_before_merge_rejected` |
| QS-05 | Повторная загрузка той же порции: повтор такта, повтор партии Planning с тем же ключом, параллельный запуск того же источника | Факты не удваиваются; параллельный запуск получает отказ блокировки, заявка выполняется следующим тактом | Сумма часов и число строк после двух загрузок совпадают; повтор Planning возвращает ту же партию; код `SOURCE_LOAD_IN_PROGRESS` | `test_pipeline.py`: `test_http_source_to_storage_idempotent_and_exact_sum`, `test_planning_replay_preserves_partial_and_missing_money`, `test_planning_duplicate_and_foreign_batch_rejected`; `test_history.py`: `test_parallel_source_job_is_rejected_before_extraction`; живой прогон `check_live_sources.py` — `rows_per_load` двух загрузок равны у всех четырёх соседей ([протокол](../pilots/artifacts/live-sources-verification.json)) |
| QS-06 | Сосед меняет формат данных, которые читает Reports | Проверка падает и называет соседа и операцию; формат вне читаемого Reports не мешает | `check_contracts.py` — код 1 и строка «<сосед> изменил контракт <файл>: <операция>» | `test_neighbour_contracts.py`; задание `neighbour-contracts` в CI |
| QS-07 | У пользователя отозвано право на денежные показатели (`cost.read`) | Отчёт по токену без права и фоновая подписка не отдают денег; файл, подготовленный до отзыва, не скачивается | Нет колонки M-09 в результате; скачивание старого файла — 403; новая доставка без денежных сумм | `test_product.py`: `test_cost_permission_in_background_and_after_revocation`, `test_money_from_owner_contract_requires_cost_permission` |

## Свежесть, измеренная на живых сервисах соседей

Порог свежести и обещание по каждому источнику — [конвейер ETL, раздел 5](etl-pipeline.md#5-свежесть-через-сколько-изменение-у-источника-видно-в-отчёте).
Замер — `pilots/check_freshness.py`: запись меняется в демо-базе соседа и возвращается после замера,
ETL работает с тактом стенда, отчёт опрашивается раз в секунду. [Протокол](../pilots/artifacts/freshness-verification.json).
