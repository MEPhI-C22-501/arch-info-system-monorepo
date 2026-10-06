CREATE TABLE currencies (
    id          BIGINT       PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code        CHAR(3)      NOT NULL,
    number      CHAR(3)      NOT NULL,
    name        VARCHAR(128) NOT NULL,
    decimals    SMALLINT     NOT NULL CHECK (decimals BETWEEN 0 AND 4),
    is_deleted  BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE currency_revisions (
    id              BIGINT       PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    currency_id     BIGINT       NOT NULL REFERENCES currencies(id) ON DELETE CASCADE,
    revision_number INTEGER      NOT NULL CHECK (revision_number >= 1),
    change          JSONB        NOT NULL,
    changed_by      UUID         NOT NULL,
    changed_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_currency_revisions_currency_revision
        UNIQUE (currency_id, revision_number)
);

CREATE UNIQUE INDEX uq_currencies_code
    ON currencies (code);

CREATE UNIQUE INDEX uq_currencies_number
    ON currencies (number);

CREATE INDEX idx_currencies_active
    ON currencies (id)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_currency_revisions_currency_id
    ON currency_revisions (currency_id);

CREATE INDEX idx_currency_revisions_covering_agg
    ON currency_revisions (currency_id, revision_number DESC)
    INCLUDE (changed_at, changed_by, change);

CREATE INDEX idx_currency_revisions_changed_at
    ON currency_revisions (changed_at);

CREATE OR REPLACE VIEW v_expanded_currency AS
SELECT
    c.id,
    c.code,
    c.number,
    c.name,
    c.decimals,
    c.is_deleted,
    agg.revision,
    agg.last_changer,
    agg.created_at,
    agg.updated_at,
    agg.deleted_at
FROM currencies c
LEFT JOIN (
    SELECT
        currency_id,
        MAX(revision_number) AS revision,
        MAX(changed_at) AS updated_at,
        (ARRAY_AGG(changed_by ORDER BY revision_number DESC))[1] AS last_changer,
        MIN(changed_at) FILTER (WHERE revision_number = 1) AS created_at,
        MAX(changed_at) FILTER (
            WHERE change @> '[{"path": "/is_deleted", "value": true}]'::jsonb
        ) AS deleted_at
    FROM currency_revisions
    GROUP BY currency_id
) agg ON agg.currency_id = c.id;

COMMENT ON TABLE currencies IS
    'ISO 4217 currency directory. Stores the current state of each currency.';

COMMENT ON COLUMN currencies.id IS
    'Internal surrogate primary key.';
COMMENT ON COLUMN currencies.code IS
    'Three-letter alphabetic currency code (e.g. USD, EUR). Always uppercase Latin.';
COMMENT ON COLUMN currencies.number IS
    'Three-digit numeric currency code stored as a string to preserve leading zeros (e.g. 008 for ALL).';
COMMENT ON COLUMN currencies.name IS
    'Official currency name in English or Russian.';
COMMENT ON COLUMN currencies.decimals IS
    'Number of minor-unit decimal places (0 for JPY, 2 for USD, 3 for BHD). Range: 0–4.';
COMMENT ON COLUMN currencies.is_deleted IS
    'Soft-delete flag. TRUE means the record has been logically removed.';

COMMENT ON TABLE currency_revisions IS
    'Immutable audit log of changes applied to currency records. Read-only from the application perspective.';

COMMENT ON COLUMN currency_revisions.id IS
    'Surrogate primary key of the revision record.';
COMMENT ON COLUMN currency_revisions.currency_id IS
    'FK referencing the currency this revision belongs to.';
COMMENT ON COLUMN currency_revisions.revision_number IS
    'Sequential revision number per currency, starting from 1.';
COMMENT ON COLUMN currency_revisions.change IS
    'JSON Patch (RFC 6902) array describing the delta from the previous revision.';
COMMENT ON COLUMN currency_revisions.changed_by IS
    'UUID of the user or system component that authored the change.';
COMMENT ON COLUMN currency_revisions.changed_at IS
    'Timestamp when the revision was applied.';

COMMENT ON VIEW v_expanded_currency IS
    'Read-only view that enriches each currency with its latest revision number, '
    'last changer UUID, and lifecycle timestamps derived from the revision log.';

COMMENT ON COLUMN v_expanded_currency.id IS
    'Internal surrogate primary key (from currencies).';
COMMENT ON COLUMN v_expanded_currency.code IS
    'Three-letter alphabetic currency code.';
COMMENT ON COLUMN v_expanded_currency.number IS
    'Three-digit numeric currency code.';
COMMENT ON COLUMN v_expanded_currency.name IS
    'Official currency name.';
COMMENT ON COLUMN v_expanded_currency.decimals IS
    'Number of minor-unit decimal places.';
COMMENT ON COLUMN v_expanded_currency.is_deleted IS
    'Soft-delete flag.';
COMMENT ON COLUMN v_expanded_currency.revision IS
    'Latest revision number applied to this currency. 0 if no revisions exist.';
COMMENT ON COLUMN v_expanded_currency.last_changer IS
    'UUID of the user or system component that performed the most recent change.';
COMMENT ON COLUMN v_expanded_currency.created_at IS
    'Timestamp of the first revision (revision_number = 1). NULL if no revisions exist.';
COMMENT ON COLUMN v_expanded_currency.updated_at IS
    'Timestamp of the most recent revision. NULL if no revisions exist.';
COMMENT ON COLUMN v_expanded_currency.deleted_at IS
    'Timestamp of the revision where is_deleted was set to TRUE. NULL if the currency has never been soft-deleted.';
