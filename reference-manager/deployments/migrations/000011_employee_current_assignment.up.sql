-- the unit and the position of an employee come from the assignment in effect today (FR-RM-49).
-- the view is created by migration 000007 before the assignments table exists, so it is replaced here
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
