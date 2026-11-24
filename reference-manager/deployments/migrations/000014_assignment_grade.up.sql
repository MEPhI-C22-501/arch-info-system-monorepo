-- the grade of an employee is a dated value of the assignment, like the unit and the position (FR-RM-69).
-- the column is added here by hand, the generated migration 000008 creates the table without it
-- (tools/gencatalog, fields with Migration: 14); empty when no grade is set
ALTER TABLE assignments
    ADD COLUMN grade_id BIGINT REFERENCES grades(id);

CREATE INDEX idx_assignments_grade_id
    ON assignments (grade_id);

-- the profile view of migration 000013 reads v_expanded_employee, so both views are replaced in place
-- with the new column after the existing ones: CREATE OR REPLACE can only append columns
CREATE OR REPLACE VIEW v_expanded_assignment AS
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
    agg.deleted_at,
    t.grade_id
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

CREATE OR REPLACE VIEW v_expanded_employee AS
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
    agg.deleted_at,
    cur.grade_id AS grade_id
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
    SELECT a.org_unit_id, a.position_id, a.grade_id
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
    'the unit, the position and the grade of the assignment in effect today and the state of the Keycloak account.';
