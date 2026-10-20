INSERT INTO currencies (code, number, name, decimals) VALUES ('RUB', '643', 'Russian Ruble', 2);
INSERT INTO currency_revisions (currency_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/code", "value": "RUB"}]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-01 10:00:00+00');

INSERT INTO org_units (code, name, kind, parent_id) VALUES ('dev', 'Development', 'DEPARTMENT', NULL);
INSERT INTO org_units (code, name, kind, parent_id) VALUES ('dev-backend', 'Backend team', 'TEAM', 1);
INSERT INTO org_unit_revisions (org_unit_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/code", "value": "dev"}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00'),
       (2, 1, '[{"op": "add", "path": "/code", "value": "dev-backend"}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');

INSERT INTO positions (code, name) VALUES ('developer', 'Software developer');
INSERT INTO position_revisions (position_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/code", "value": "developer"}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');

INSERT INTO employees (personnel_number, family_name, given_name, middle_name, email, username, hire_date)
VALUES ('1001', 'Ivanov', 'Ivan', 'Ivanovich', 'i.ivanov@example.org', 'i.ivanov', '2024-01-15');
INSERT INTO employee_revisions (employee_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/personnel_number", "value": "1001"}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');
