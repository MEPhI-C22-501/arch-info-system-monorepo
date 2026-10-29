-- the Keycloak account of an employee (FR-RM-53..58): its state and its identifier, the sub claim of its tokens.
-- the columns are added here by hand, the generated migration 000007 creates the table without them
-- (tools/gencatalog, fields with Migration: 12)
ALTER TABLE employees
    ADD COLUMN account_state TEXT CHECK (account_state IN ('PENDING', 'ENABLED', 'DISABLED')) NOT NULL DEFAULT 'PENDING',
    ADD COLUMN account_user_id VARCHAR(36);

-- one account belongs to one employee
CREATE UNIQUE INDEX uq_employees_account_user_id
    ON employees (account_user_id)
    WHERE account_user_id IS NOT NULL;

CREATE INDEX idx_employees_account_state
    ON employees (account_state)
    WHERE is_deleted = FALSE;

-- the view of migration 000011 with the account columns after the computed ones,
-- CREATE OR REPLACE cannot add columns in the middle, so the view is created anew
DROP VIEW IF EXISTS v_expanded_employee;

CREATE VIEW v_expanded_employee AS
SELECT
    t.id,
    t.personnel_number,
    t.family_name,
    t.given_name,
    t.middle_name,
    t.email,
    t.username,
    t.hire_date,
    t.employment_state,
    t.dismissal_date,
    cur.org_unit_id AS org_unit_id,
    cur.position_id AS position_id,
    t.account_state,
    t.account_user_id,
    t.is_deleted,
    agg.revision,
    agg.last_changer,
    agg.created_at,
    agg.updated_at,
    agg.deleted_at
FROM employees t
LEFT JOIN (
    SELECT
        employee_id,
        MAX(revision_number) AS revision,
        MAX(changed_at) AS updated_at,
        (ARRAY_AGG(changed_by ORDER BY revision_number DESC))[1] AS last_changer,
        MIN(changed_at) FILTER (WHERE revision_number = 1) AS created_at,
        MAX(changed_at) FILTER (
            WHERE change @> '[{"path": "/is_deleted", "value": true}]'::jsonb
        ) AS deleted_at
    FROM employee_revisions
    GROUP BY employee_id
) agg ON agg.employee_id = t.id
LEFT JOIN LATERAL (
    SELECT a.org_unit_id, a.position_id
    FROM assignments a
    WHERE a.employee_id = t.id
      AND NOT a.is_deleted
      AND a.start_date <= CURRENT_DATE
      AND (a.end_date IS NULL OR a.end_date >= CURRENT_DATE)
    ORDER BY a.start_date DESC
    LIMIT 1
) cur ON TRUE;

COMMENT ON VIEW v_expanded_employee IS
    'Read-only view that enriches each employee with its latest revision number, '
    'last changer UUID, lifecycle timestamps derived from the revision log, '
    'the unit and the position of the assignment in effect today and the state of the Keycloak account.';
