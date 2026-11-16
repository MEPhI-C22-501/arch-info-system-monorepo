CREATE TABLE user_profiles (
    issuer TEXT NOT NULL,
    subject UUID NOT NULL,
    display_name TEXT NOT NULL CHECK (btrim(display_name) <> ''),
    work_email TEXT,
    is_technical BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (issuer, subject)
);

CREATE VIEW v_employee_profile AS
SELECT
    'e:' || lpad(e.id::text, 20, '0') AS profile_key,
    e.id AS employee_id,
    e.account_user_id AS user_id,
    concat_ws(' ', nullif(btrim(e.family_name), ''), nullif(btrim(e.given_name), ''),
                   nullif(btrim(e.middle_name), '')) AS display_name,
    e.email AS work_email,
    e.org_unit_id, o.name AS org_unit_name,
    e.position_id, p.name AS position_name,
    e.employment_state, e.account_state, e.is_deleted,
    FALSE AS is_technical,
    NOT e.is_deleted AND e.employment_state = 'EMPLOYED' AS is_active,
    greatest(e.updated_at, o.updated_at, p.updated_at) AS updated_at
FROM v_expanded_employee e
LEFT JOIN v_expanded_org_unit o ON e.org_unit_id = o.id
LEFT JOIN v_expanded_position p ON e.position_id = p.id;
