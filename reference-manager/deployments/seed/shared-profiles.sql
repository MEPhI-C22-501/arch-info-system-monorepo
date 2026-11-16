-- Links for the disposable shared stand. The subject IDs are imported by keycloak_converge.py.
WITH bindings(personnel_number, subject) AS (
    VALUES ('1004', '11111111-1111-1111-1111-111111111111'),
           ('1008', '22222222-2222-2222-2222-222222222222')
), linked AS (
    UPDATE employees e
    SET account_user_id = b.subject, account_state = 'ENABLED'
    FROM bindings b
    WHERE e.personnel_number = b.personnel_number AND e.account_user_id IS NULL
    RETURNING e.id, e.account_user_id
)
INSERT INTO employee_revisions (employee_id, revision_number, change, changed_by)
SELECT id, (SELECT max(revision_number) FROM employee_revisions WHERE employee_id = linked.id) + 1,
       jsonb_build_array(jsonb_build_object('op', 'replace', 'path', '/account_user_id', 'value', account_user_id),
                        jsonb_build_object('op', 'replace', 'path', '/account_state', 'value', 'ENABLED')),
       '33333333-3333-3333-3333-333333333333'
FROM linked;

INSERT INTO user_profiles (issuer, subject, display_name)
VALUES ('http://localhost:8081/realms/arch-info-system', '33333333-3333-3333-3333-333333333333', 'Демо Администратор')
ON CONFLICT DO NOTHING;
