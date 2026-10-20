-- restores the view of migration 000007 without the assignment in effect
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
    NULL::bigint AS org_unit_id,
    NULL::bigint AS position_id,
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
) agg ON agg.employee_id = t.id;
