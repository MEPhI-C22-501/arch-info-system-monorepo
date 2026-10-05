CREATE TABLE status (
  id uuid PRIMARY KEY, name text NOT NULL UNIQUE, board_order integer NOT NULL,
  active boolean NOT NULL DEFAULT true, board_visible boolean NOT NULL DEFAULT true,
  category text NOT NULL CHECK (category IN ('OPEN','COMPLETED','ARCHIVED'))
);
CREATE TABLE priority (
  id uuid PRIMARY KEY, name text NOT NULL UNIQUE, sort_order integer NOT NULL,
  active boolean NOT NULL DEFAULT true, code text UNIQUE
);
CREATE TABLE severity_priority (
  severity text PRIMARY KEY CHECK (severity IN ('critical','high','medium','low')),
  priority_id uuid NOT NULL REFERENCES priority(id)
);
CREATE TABLE type_setting (
  type text PRIMARY KEY CHECK (type IN ('PROJECT','EPIC','TASK','BUG','SUBTASK')),
  enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE role_permission (
  role text NOT NULL, permission text NOT NULL, allowed boolean NOT NULL,
  PRIMARY KEY (role, permission)
);
CREATE TABLE local_access (
  external_user_id text PRIMARY KEY, role text NOT NULL CHECK (role IN ('MEMBER','LEAD','ADMIN')),
  allowed boolean NOT NULL DEFAULT true
);
CREATE TABLE directory_meta (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton), version text,
  last_success_at timestamptz
);
INSERT INTO directory_meta(singleton) VALUES (true);
CREATE TABLE directory_team (external_id text PRIMARY KEY, display_name text NOT NULL, active boolean NOT NULL);
CREATE TABLE directory_department (external_id text PRIMARY KEY, display_name text NOT NULL, active boolean NOT NULL);
CREATE TABLE user_cache (
  external_user_id text PRIMARY KEY, display_name text NOT NULL, team_external_id text,
  department_external_id text, active boolean NOT NULL, synced_at timestamptz NOT NULL
);
CREATE TABLE sync_log (
  id uuid PRIMARY KEY, occurred_at timestamptz NOT NULL, duration_ms bigint NOT NULL,
  success boolean NOT NULL, correlation_id text NOT NULL, message text NOT NULL
);
CREATE TABLE integration_request_log (
  id uuid PRIMARY KEY, occurred_at timestamptz NOT NULL, duration_ms bigint NOT NULL,
  correlation_id text NOT NULL, method text NOT NULL, path text NOT NULL,
  status_code integer NOT NULL
);
CREATE INDEX idx_integration_request_occurred ON integration_request_log(occurred_at DESC);
CREATE TABLE work_item (
  id uuid PRIMARY KEY, type text NOT NULL CHECK (type IN ('PROJECT','EPIC','TASK','BUG','SUBTASK')),
  title text NOT NULL CHECK (length(btrim(title)) > 0), description text NOT NULL DEFAULT '',
  status_id uuid NOT NULL REFERENCES status(id), priority_id uuid NOT NULL REFERENCES priority(id),
  assignee_external_id text, start_date date, due_date date,
  planned_hours numeric(12,2) CHECK (planned_hours >= 0),
  parent_id uuid REFERENCES work_item(id) ON DELETE RESTRICT,
  external_source text, external_defect_id text, severity text, environment text,
  test_run_url text, test_case_url text, version bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
  CHECK (due_date IS NULL OR start_date IS NULL OR due_date >= start_date),
  UNIQUE (external_source, external_defect_id)
);
CREATE INDEX idx_work_item_status ON work_item(status_id);
CREATE INDEX idx_work_item_priority ON work_item(priority_id);
CREATE INDEX idx_work_item_assignee ON work_item(assignee_external_id);
CREATE INDEX idx_work_item_parent ON work_item(parent_id);
CREATE TABLE iteration (
  id uuid PRIMARY KEY, name text NOT NULL, description text NOT NULL DEFAULT '',
  start_date date NOT NULL, end_date date NOT NULL, state text NOT NULL CHECK (state IN ('PLANNED','ACTIVE','COMPLETED')),
  baseline_snapshot jsonb, result_snapshot jsonb, created_at timestamptz NOT NULL,
  CHECK (end_date >= start_date)
);
CREATE TABLE work_item_iteration (
  id uuid PRIMARY KEY, iteration_id uuid NOT NULL REFERENCES iteration(id),
  work_item_id uuid NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
  added_at timestamptz NOT NULL, removed_at timestamptz
);
CREATE INDEX idx_membership_active ON work_item_iteration(work_item_id) WHERE removed_at IS NULL;
CREATE INDEX idx_membership_iteration ON work_item_iteration(iteration_id);
CREATE TABLE capacity_entry (
  iteration_id uuid NOT NULL REFERENCES iteration(id), external_user_id text NOT NULL,
  available_hours numeric(12,2) NOT NULL CHECK (available_hours >= 0),
  PRIMARY KEY(iteration_id, external_user_id)
);
CREATE TABLE time_log_entry (
  id uuid PRIMARY KEY, work_item_id uuid NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
  external_user_id text NOT NULL, logged_date date NOT NULL, hours numeric(12,2) NOT NULL CHECK (hours > 0),
  comment text NOT NULL DEFAULT '', created_at timestamptz NOT NULL
);
CREATE INDEX idx_time_log_item ON time_log_entry(work_item_id);
CREATE TABLE comment (
  id uuid PRIMARY KEY, work_item_id uuid NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
  author_external_id text NOT NULL, body text NOT NULL CHECK (length(btrim(body)) > 0),
  created_at timestamptz NOT NULL
);
CREATE TABLE attachment (
  id uuid PRIMARY KEY, work_item_id uuid NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
  file_name text NOT NULL, size_bytes bigint NOT NULL, content_type text NOT NULL,
  content bytea NOT NULL, uploaded_by_external_id text NOT NULL, uploaded_at timestamptz NOT NULL
);
CREATE TABLE audit_entry (
  id uuid PRIMARY KEY, work_item_id uuid NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
  actor_external_id text, external_source text, occurred_at timestamptz NOT NULL,
  changed_fields jsonb NOT NULL, old_values jsonb NOT NULL, new_values jsonb NOT NULL
);
CREATE INDEX idx_audit_item ON audit_entry(work_item_id, occurred_at);
CREATE TABLE notification (
  id uuid PRIMARY KEY, recipient_external_id text NOT NULL,
  work_item_id uuid REFERENCES work_item(id) ON DELETE SET NULL,
  work_item_public_id text NOT NULL, work_item_title text NOT NULL,
  message text NOT NULL, actor text NOT NULL, created_at timestamptz NOT NULL, read_at timestamptz
);
CREATE INDEX idx_notification_recipient ON notification(recipient_external_id, created_at DESC);

INSERT INTO status(id,name,board_order,active,board_visible,category) VALUES
('00000000-0000-0000-0000-000000000101','Бэклог',1,true,true,'OPEN'),
('00000000-0000-0000-0000-000000000102','В работе',2,true,true,'OPEN'),
('00000000-0000-0000-0000-000000000103','На проверке',3,true,true,'OPEN'),
('00000000-0000-0000-0000-000000000104','Завершена',4,true,true,'COMPLETED'),
('00000000-0000-0000-0000-000000000105','Архивирована',5,true,false,'ARCHIVED');
INSERT INTO priority(id,name,sort_order,active,code) VALUES
('00000000-0000-0000-0000-000000000201','Критический',1,true,'critical'),
('00000000-0000-0000-0000-000000000202','Высокий',2,true,'high'),
('00000000-0000-0000-0000-000000000203','Средний',3,true,'medium'),
('00000000-0000-0000-0000-000000000204','Низкий',4,true,'low');
INSERT INTO severity_priority(severity,priority_id) VALUES
('critical','00000000-0000-0000-0000-000000000201'),
('high','00000000-0000-0000-0000-000000000202'),
('medium','00000000-0000-0000-0000-000000000203'),
('low','00000000-0000-0000-0000-000000000204');
INSERT INTO type_setting(type,enabled) VALUES ('PROJECT',true),('EPIC',true),('TASK',true),('BUG',true),('SUBTASK',true);
INSERT INTO role_permission(role,permission,allowed)
SELECT roles.role, permissions.permission, true
FROM (VALUES ('MEMBER'),('LEAD'),('ADMIN')) roles(role)
CROSS JOIN (VALUES ('item.read'),('iteration.read'),('notifications.read')) permissions(permission);
INSERT INTO role_permission(role,permission,allowed)
SELECT roles.role, permissions.permission, true
FROM (VALUES ('MEMBER'),('LEAD')) roles(role)
CROSS JOIN (VALUES ('item.create'),('item.update'),('item.status'),('comment.create'),('attachment.create'),('attachment.delete'),('time.create')) permissions(permission);
INSERT INTO role_permission(role,permission,allowed)
SELECT 'LEAD', permission, true FROM (VALUES ('iteration.write'),('capacity.write'),('excel.export'),('excel.import'),('comment.manage')) p(permission);
INSERT INTO role_permission(role,permission,allowed)
SELECT 'ADMIN', permission, true FROM (VALUES ('item.delete'),('status.admin'),('priority.admin'),('type.admin'),('access.admin'),('directory.admin'),('comment.manage')) p(permission);
