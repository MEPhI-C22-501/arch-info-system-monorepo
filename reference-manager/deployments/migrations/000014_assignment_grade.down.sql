-- back to the views of migrations 000008 and 000012 without the grade. CREATE OR REPLACE cannot drop a column,
-- so the views are created anew, with the profile view of migration 000013 that reads the employee view
DROP VIEW IF EXISTS v_employee_profile;
DROP VIEW IF EXISTS v_expanded_employee;
DROP VIEW IF EXISTS v_expanded_assignment;

CREATE VIEW v_expanded_assignment AS
SELECT
    t.id,
    t.employee_id,
    t.org_unit_id,
    t.position_id,
    t.start_date,
    t.end_date,
    t.is_deleted,
    agg.revision,
    agg.last_changer,
    agg.created_at,
    agg.updated_at,
    agg.deleted_at
FROM assignments t
LEFT JOIN (
    SELECT
        assignment_id,
        MAX(revision_number) AS revision,
        MAX(changed_at) AS updated_at,
        (ARRAY_AGG(changed_by ORDER BY revision_number DESC))[1] AS last_changer,
        MIN(changed_at) FILTER (WHERE revision_number = 1) AS created_at,
        MAX(changed_at) FILTER (
            WHERE change @> '[{"path": "/is_deleted", "value": true}]'::jsonb
        ) AS deleted_at
    FROM assignment_revisions
    GROUP BY assignment_id
) agg ON agg.assignment_id = t.id;

COMMENT ON VIEW v_expanded_assignment IS
    'Read-only view that enriches each assignment with its latest revision number, '
    'last changer UUID, and lifecycle timestamps derived from the revision log.';

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

DROP INDEX IF EXISTS idx_assignments_grade_id;

ALTER TABLE assignments
    DROP COLUMN IF EXISTS grade_id;
