DROP VIEW IF EXISTS v_expanded_currency;

DROP INDEX IF EXISTS uq_currencies_code;
DROP INDEX IF EXISTS uq_currencies_number;
DROP INDEX IF EXISTS idx_currencies_active;

DROP INDEX IF EXISTS idx_currency_revisions_currency_id;
DROP INDEX IF EXISTS idx_currency_revisions_covering_agg;
DROP INDEX IF EXISTS idx_currency_revisions_changed_at;

DROP TABLE IF EXISTS currency_revisions;

DROP TABLE IF EXISTS currencies;