CREATE TABLE currency (
  id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  code_alpha char(3) NOT NULL,
  code_num char(3) NOT NULL,
  name varchar(100) NOT NULL,
  minor_units smallint NOT NULL DEFAULT 2 CONSTRAINT chk_minor_units CHECK (minor_units BETWEEN 0 AND 4),
  symbol varchar(10) NOT NULL DEFAULT '',
  CONSTRAINT uq_currency_code_alpha UNIQUE (code_alpha),
  CONSTRAINT uq_currency_code_num UNIQUE (code_num)
);

COMMENT ON TABLE currency IS 'Currency dictionary aligned with the ISO 4217 international standard';
COMMENT ON COLUMN currency.id IS 'Unique internal identifier (surrogate primary key)';
COMMENT ON COLUMN currency.code_alpha IS 'Three-letter currency code as per ISO 4217 (e.g., USD, EUR, RUB)';
COMMENT ON COLUMN currency.code_num IS 'Three-digit numeric currency code as per ISO 4217 (e.g., 840, 978, 643)';
COMMENT ON COLUMN currency.name IS 'Official name of the currency';
COMMENT ON COLUMN currency.minor_units IS 'Number of decimal places for the currency fractional unit. Usually 2, 0 for JPY, 3 for TND';
COMMENT ON COLUMN currency.symbol IS 'Graphical symbol of the currency used for user interfaces (e.g., $, €, ₽)';

CREATE TABLE currency_revision (
  id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  currency_id bigint NOT NULL,
  revision int NOT NULL,
  change jsonb NOT NULL,
  changed_by uuid NOT NULL,
  changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT fk_currency_revision_currency FOREIGN KEY (currency_id) REFERENCES currency(id) ON DELETE CASCADE,
  CONSTRAINT uq_currency_currency_id_revision UNIQUE (currency_id, revision)
);

CREATE INDEX idx_currency_revision_currency_id_rev ON currency_revision (currency_id, revision DESC);

COMMENT ON TABLE currency_revision IS 'Revision history of currency records. Each currency has at least one revision, created together with the currency record';
COMMENT ON COLUMN currency_revision.id IS 'Unique identifier of the revision record';
COMMENT ON COLUMN currency_revision.currency_id IS 'Identifier of the currency record this revision belongs to';
COMMENT ON COLUMN currency_revision.revision IS 'Sequential revision number of the currency record, starting at 1';
COMMENT ON COLUMN currency_revision.change IS 'RFC 6902 JSON Patch describing the changes introduced by this revision';
COMMENT ON COLUMN currency_revision.changed_by IS 'UUID of the user or system service that created this revision';
COMMENT ON COLUMN currency_revision.changed_at IS 'Timestamp when this revision was created';

CREATE OR REPLACE VIEW v_expanded_currency AS
WITH currency_history_summary AS (
  SELECT 
    currency_id,
    MAX(revision) AS revision,
    (array_agg(changed_by ORDER BY revision DESC))[1] AS last_changer,
    MIN(changed_at) AS created_at,
    MAX(changed_at) AS updated_at
  FROM currency_revision
  GROUP BY currency_id
)
SELECT 
  c.id,
  c.code_alpha,
  c.code_num,
  c.name,
  c.minor_units,
  c.symbol,
  h.revision,
  h.last_changer,
  h.created_at,
  h.updated_at
FROM currency c
LEFT JOIN currency_history_summary h ON c.id = h.currency_id;

COMMENT ON VIEW v_expanded_currency IS 'Extended currency view combining the current currency state with metadata derived from its revision history';
COMMENT ON COLUMN v_expanded_currency.id IS 'Currency identifier';
COMMENT ON COLUMN v_expanded_currency.code_alpha IS 'Three-letter currency code as defined by ISO 4217';
COMMENT ON COLUMN v_expanded_currency.code_num IS 'Three-digit numeric currency code as defined by ISO 4217';
COMMENT ON COLUMN v_expanded_currency.name IS 'Official name of the currency';
COMMENT ON COLUMN v_expanded_currency.minor_units IS 'Number of decimal places used for the currency fractional unit';
COMMENT ON COLUMN v_expanded_currency.symbol IS 'Graphical symbol of the currency used in user interfaces';
COMMENT ON COLUMN v_expanded_currency.revision IS 'Current revision number of the currency record';
COMMENT ON COLUMN v_expanded_currency.last_changer IS 'UUID of the user or system service that created the latest revision';
COMMENT ON COLUMN v_expanded_currency.created_at IS 'Timestamp when the first revision of the currency record was created';
COMMENT ON COLUMN v_expanded_currency.updated_at IS 'Timestamp when the latest revision of the currency record was created';