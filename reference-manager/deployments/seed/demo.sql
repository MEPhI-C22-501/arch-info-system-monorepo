-- demonstration data set of the local environment, loaded by `task demo:data` (compose service reference-manager-seed)
-- after the migrations, skipped when employees exist, so a repeated load changes nothing,
-- every record gets its first revision as the service writes it, so the history and the lifecycle fields are complete,
-- the Keycloak accounts of the employees are created afterwards by `task demo:accounts` through the API
DO $$
DECLARE
    admin_user    CONSTANT uuid := '3fa85f64-5717-4562-b3fc-2c963f66afa6';
    hr_admin_user CONSTANT uuid := 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d';
    loaded_at     CONSTANT timestamptz := '2026-10-01 09:00:00+00';
BEGIN
    IF EXISTS (SELECT 1 FROM employees) THEN
        RAISE NOTICE 'demo data: employees exist, nothing loaded';
        RETURN;
    END IF;

    -- classifiers (G-1), maintained by reference-admin

    INSERT INTO currencies (code, number, name, decimals) VALUES
        ('RUB', '643', 'Российский рубль', 2),
        ('USD', '840', 'Доллар США', 2),
        ('EUR', '978', 'Евро', 2)
    ON CONFLICT DO NOTHING;

    INSERT INTO currency_revisions (currency_id, revision_number, change, changed_by, changed_at)
    SELECT c.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/code', 'value', c.code),
        jsonb_build_object('op', 'add', 'path', '/number', 'value', c.number),
        jsonb_build_object('op', 'add', 'path', '/name', 'value', c.name),
        jsonb_build_object('op', 'add', 'path', '/decimals', 'value', c.decimals),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), admin_user, loaded_at
    FROM currencies c
    WHERE NOT EXISTS (SELECT 1 FROM currency_revisions r WHERE r.currency_id = c.id);

    INSERT INTO countries (alpha2, alpha3, numeric_code, name, currency_id) VALUES
        ('RU', 'RUS', '643', 'Россия', (SELECT id FROM currencies WHERE code = 'RUB')),
        ('BY', 'BLR', '112', 'Беларусь', NULL),
        ('KZ', 'KAZ', '398', 'Казахстан', NULL),
        ('US', 'USA', '840', 'США', (SELECT id FROM currencies WHERE code = 'USD')),
        ('DE', 'DEU', '276', 'Германия', (SELECT id FROM currencies WHERE code = 'EUR'))
    ON CONFLICT DO NOTHING;

    INSERT INTO country_revisions (country_id, revision_number, change, changed_by, changed_at)
    SELECT c.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/alpha2', 'value', c.alpha2),
        jsonb_build_object('op', 'add', 'path', '/alpha3', 'value', c.alpha3),
        jsonb_build_object('op', 'add', 'path', '/numeric_code', 'value', c.numeric_code),
        jsonb_build_object('op', 'add', 'path', '/name', 'value', c.name),
        jsonb_build_object('op', 'add', 'path', '/currency_id', 'value', c.currency_id),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), admin_user, loaded_at
    FROM countries c
    WHERE NOT EXISTS (SELECT 1 FROM country_revisions r WHERE r.country_id = c.id);

    INSERT INTO project_roles (code, name, description) VALUES
        ('developer', 'Разработчик', 'Проектирует и реализует функциональность'),
        ('qa-engineer', 'Тестировщик', 'Проверяет качество и ведёт дефекты'),
        ('analyst', 'Аналитик', 'Собирает и описывает требования'),
        ('project-manager', 'Руководитель проекта', 'Планирует работы и отвечает за результат'),
        ('devops', 'Инженер DevOps', 'Отвечает за сборку, поставку и среды')
    ON CONFLICT DO NOTHING;

    INSERT INTO project_role_revisions (project_role_id, revision_number, change, changed_by, changed_at)
    SELECT p.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/code', 'value', p.code),
        jsonb_build_object('op', 'add', 'path', '/name', 'value', p.name),
        jsonb_build_object('op', 'add', 'path', '/description', 'value', p.description),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), admin_user, loaded_at
    FROM project_roles p
    WHERE NOT EXISTS (SELECT 1 FROM project_role_revisions r WHERE r.project_role_id = p.id);

    INSERT INTO grades (code, name, rank) VALUES
        ('junior', 'Junior', 1),
        ('middle', 'Middle', 2),
        ('senior', 'Senior', 3),
        ('lead', 'Lead', 4)
    ON CONFLICT DO NOTHING;

    INSERT INTO grade_revisions (grade_id, revision_number, change, changed_by, changed_at)
    SELECT g.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/code', 'value', g.code),
        jsonb_build_object('op', 'add', 'path', '/name', 'value', g.name),
        jsonb_build_object('op', 'add', 'path', '/rank', 'value', g.rank),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), admin_user, loaded_at
    FROM grades g
    WHERE NOT EXISTS (SELECT 1 FROM grade_revisions r WHERE r.grade_id = g.id);

    -- HR catalogs (G-2), maintained by reference-hr-admin

    INSERT INTO org_units (code, name, kind, parent_id) VALUES
        ('dev', 'Департамент разработки', 'DEPARTMENT', NULL),
        ('qa', 'Отдел тестирования', 'DEPARTMENT', NULL),
        ('hr', 'Отдел кадров', 'DEPARTMENT', NULL),
        ('pmo', 'Проектный офис', 'DEPARTMENT', NULL)
    ON CONFLICT DO NOTHING;

    INSERT INTO org_units (code, name, kind, parent_id) VALUES
        ('dev-backend', 'Команда backend', 'TEAM', (SELECT id FROM org_units WHERE code = 'dev')),
        ('dev-frontend', 'Команда frontend', 'TEAM', (SELECT id FROM org_units WHERE code = 'dev'))
    ON CONFLICT DO NOTHING;

    INSERT INTO org_unit_revisions (org_unit_id, revision_number, change, changed_by, changed_at)
    SELECT u.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/code', 'value', u.code),
        jsonb_build_object('op', 'add', 'path', '/name', 'value', u.name),
        jsonb_build_object('op', 'add', 'path', '/kind', 'value', u.kind),
        jsonb_build_object('op', 'add', 'path', '/parent_id', 'value', u.parent_id),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), hr_admin_user, loaded_at
    FROM org_units u
    WHERE NOT EXISTS (SELECT 1 FROM org_unit_revisions r WHERE r.org_unit_id = u.id);

    INSERT INTO positions (code, name) VALUES
        ('developer', 'Разработчик'),
        ('senior-developer', 'Старший разработчик'),
        ('team-lead', 'Руководитель команды'),
        ('qa-engineer', 'Инженер по тестированию'),
        ('hr-manager', 'Менеджер по персоналу'),
        ('project-manager', 'Руководитель проекта'),
        ('analyst', 'Аналитик')
    ON CONFLICT DO NOTHING;

    INSERT INTO position_revisions (position_id, revision_number, change, changed_by, changed_at)
    SELECT p.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/code', 'value', p.code),
        jsonb_build_object('op', 'add', 'path', '/name', 'value', p.name),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), hr_admin_user, loaded_at
    FROM positions p
    WHERE NOT EXISTS (SELECT 1 FROM position_revisions r WHERE r.position_id = p.id);

    -- the accounts are PENDING until `task demo:accounts` creates them in Keycloak
    INSERT INTO employees (personnel_number, family_name, given_name, middle_name, email, username, hire_date) VALUES
        ('1001', 'Иванов', 'Иван', 'Иванович', 'i.ivanov@example.org', 'i.ivanov', '2022-03-01'),
        ('1002', 'Петрова', 'Мария', 'Сергеевна', 'm.petrova@example.org', 'm.petrova', '2023-06-15'),
        ('1003', 'Сидоров', 'Алексей', 'Петрович', 'a.sidorov@example.org', 'a.sidorov', '2021-09-01'),
        ('1004', 'Кузнецова', 'Анна', 'Викторовна', 'a.kuznetsova@example.org', 'a.kuznetsova', '2024-02-12'),
        ('1005', 'Смирнов', 'Дмитрий', 'Олегович', 'd.smirnov@example.org', 'd.smirnov', '2024-11-05'),
        ('1006', 'Новикова', 'Елена', 'Андреевна', 'e.novikova@example.org', 'e.novikova', '2020-01-20'),
        ('1007', 'Морозов', 'Павел', 'Игоревич', 'p.morozov@example.org', 'p.morozov', '2025-04-01'),
        ('1008', 'Волкова', 'Ольга', 'Николаевна', 'o.volkova@example.org', 'o.volkova', '2023-01-09');

    INSERT INTO employee_revisions (employee_id, revision_number, change, changed_by, changed_at)
    SELECT e.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/personnel_number', 'value', e.personnel_number),
        jsonb_build_object('op', 'add', 'path', '/family_name', 'value', e.family_name),
        jsonb_build_object('op', 'add', 'path', '/given_name', 'value', e.given_name),
        jsonb_build_object('op', 'add', 'path', '/middle_name', 'value', e.middle_name),
        jsonb_build_object('op', 'add', 'path', '/email', 'value', e.email),
        jsonb_build_object('op', 'add', 'path', '/username', 'value', e.username),
        jsonb_build_object('op', 'add', 'path', '/hire_date', 'value', to_char(e.hire_date, 'YYYY-MM-DD') || 'T00:00:00Z'),
        jsonb_build_object('op', 'add', 'path', '/employment_state', 'value', e.employment_state),
        jsonb_build_object('op', 'add', 'path', '/dismissal_date', 'value', NULL),
        jsonb_build_object('op', 'add', 'path', '/account_state', 'value', e.account_state),
        jsonb_build_object('op', 'add', 'path', '/account_user_id', 'value', NULL),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), hr_admin_user, loaded_at
    FROM employees e;

    -- dated records: one open period per employee, Petrova has a closed one before the current (BR-RM-16)

    INSERT INTO assignments (employee_id, org_unit_id, position_id, start_date, end_date) VALUES
        ((SELECT id FROM employees WHERE personnel_number = '1001'), (SELECT id FROM org_units WHERE code = 'dev-backend'), (SELECT id FROM positions WHERE code = 'team-lead'), '2022-03-01', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1002'), (SELECT id FROM org_units WHERE code = 'dev-backend'), (SELECT id FROM positions WHERE code = 'developer'), '2023-06-15', '2024-12-31'),
        ((SELECT id FROM employees WHERE personnel_number = '1002'), (SELECT id FROM org_units WHERE code = 'dev-backend'), (SELECT id FROM positions WHERE code = 'senior-developer'), '2025-01-01', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1003'), (SELECT id FROM org_units WHERE code = 'dev-frontend'), (SELECT id FROM positions WHERE code = 'senior-developer'), '2021-09-01', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1004'), (SELECT id FROM org_units WHERE code = 'qa'), (SELECT id FROM positions WHERE code = 'qa-engineer'), '2024-02-12', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1005'), (SELECT id FROM org_units WHERE code = 'dev-backend'), (SELECT id FROM positions WHERE code = 'developer'), '2024-11-05', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1006'), (SELECT id FROM org_units WHERE code = 'hr'), (SELECT id FROM positions WHERE code = 'hr-manager'), '2020-01-20', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1007'), (SELECT id FROM org_units WHERE code = 'pmo'), (SELECT id FROM positions WHERE code = 'analyst'), '2025-04-01', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1008'), (SELECT id FROM org_units WHERE code = 'pmo'), (SELECT id FROM positions WHERE code = 'project-manager'), '2023-01-09', NULL);

    INSERT INTO assignment_revisions (assignment_id, revision_number, change, changed_by, changed_at)
    SELECT a.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/employee_id', 'value', a.employee_id),
        jsonb_build_object('op', 'add', 'path', '/org_unit_id', 'value', a.org_unit_id),
        jsonb_build_object('op', 'add', 'path', '/position_id', 'value', a.position_id),
        jsonb_build_object('op', 'add', 'path', '/start_date', 'value', to_char(a.start_date, 'YYYY-MM-DD') || 'T00:00:00Z'),
        jsonb_build_object('op', 'add', 'path', '/end_date', 'value', CASE WHEN a.end_date IS NULL THEN NULL ELSE to_char(a.end_date, 'YYYY-MM-DD') || 'T00:00:00Z' END),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), hr_admin_user, loaded_at
    FROM assignments a;

    INSERT INTO salaries (employee_id, amount, currency_id, start_date, end_date) VALUES
        ((SELECT id FROM employees WHERE personnel_number = '1001'), 320000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2022-03-01', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1002'), 180000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2023-06-15', '2024-12-31'),
        ((SELECT id FROM employees WHERE personnel_number = '1002'), 240000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2025-01-01', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1003'), 260000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2021-09-01', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1004'), 150000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2024-02-12', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1005'), 160000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2024-11-05', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1006'), 140000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2020-01-20', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1007'), 170000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2025-04-01', NULL),
        ((SELECT id FROM employees WHERE personnel_number = '1008'), 290000.00, (SELECT id FROM currencies WHERE code = 'RUB'), '2023-01-09', NULL);

    INSERT INTO salary_revisions (salary_id, revision_number, change, changed_by, changed_at)
    SELECT s.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/employee_id', 'value', s.employee_id),
        jsonb_build_object('op', 'add', 'path', '/amount', 'value', s.amount),
        jsonb_build_object('op', 'add', 'path', '/currency_id', 'value', s.currency_id),
        jsonb_build_object('op', 'add', 'path', '/start_date', 'value', to_char(s.start_date, 'YYYY-MM-DD') || 'T00:00:00Z'),
        jsonb_build_object('op', 'add', 'path', '/end_date', 'value', CASE WHEN s.end_date IS NULL THEN NULL ELSE to_char(s.end_date, 'YYYY-MM-DD') || 'T00:00:00Z' END),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), hr_admin_user, loaded_at
    FROM salaries s;

    INSERT INTO absences (employee_id, kind, start_date, end_date) VALUES
        ((SELECT id FROM employees WHERE personnel_number = '1002'), 'VACATION', '2026-07-01', '2026-07-14'),
        ((SELECT id FROM employees WHERE personnel_number = '1004'), 'SICK_LEAVE', '2026-09-10', '2026-09-16'),
        ((SELECT id FROM employees WHERE personnel_number = '1007'), 'VACATION', '2026-12-21', '2026-12-31'),
        ((SELECT id FROM employees WHERE personnel_number = '1001'), 'OTHER', '2026-11-03', '2026-11-03');

    INSERT INTO absence_revisions (absence_id, revision_number, change, changed_by, changed_at)
    SELECT b.id, 1, jsonb_build_array(
        jsonb_build_object('op', 'add', 'path', '/employee_id', 'value', b.employee_id),
        jsonb_build_object('op', 'add', 'path', '/kind', 'value', b.kind),
        jsonb_build_object('op', 'add', 'path', '/start_date', 'value', to_char(b.start_date, 'YYYY-MM-DD') || 'T00:00:00Z'),
        jsonb_build_object('op', 'add', 'path', '/end_date', 'value', to_char(b.end_date, 'YYYY-MM-DD') || 'T00:00:00Z'),
        jsonb_build_object('op', 'add', 'path', '/is_deleted', 'value', false)
    ), hr_admin_user, loaded_at
    FROM absences b;

    RAISE NOTICE 'demo data loaded: % employees', (SELECT count(*) FROM employees);
END $$;
