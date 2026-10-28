-- Manual fixture for a migrated development database; IDs are stable for Infra.
BEGIN;
INSERT INTO work_item(id,type,title,status_id,priority_id,assignee_external_id,parent_id,planned_hours,created_at,updated_at) VALUES
('dddddddd-0000-0000-0000-000000000001','PROJECT','Демо проект','00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000203','22222222-2222-2222-2222-222222222222',NULL,NULL,now(),now()),
('dddddddd-0000-0000-0000-000000000002','EPIC','Демо эпик','00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000203','22222222-2222-2222-2222-222222222222','dddddddd-0000-0000-0000-000000000001',NULL,now(),now()),
('dddddddd-0000-0000-0000-000000000003','TASK','Демо задача в работе','00000000-0000-0000-0000-000000000102','00000000-0000-0000-0000-000000000203','11111111-1111-1111-1111-111111111111','dddddddd-0000-0000-0000-000000000002',8,now(),now()),
('dddddddd-0000-0000-0000-000000000004','TASK','Демо завершённая задача','00000000-0000-0000-0000-000000000104','00000000-0000-0000-0000-000000000203','11111111-1111-1111-1111-111111111111','dddddddd-0000-0000-0000-000000000002',4,now(),now())
ON CONFLICT(id) DO NOTHING;
INSERT INTO iteration(id,name,start_date,end_date,state,created_at) VALUES
('dddddddd-0000-0000-0000-000000000010','Демо итерация',current_date,current_date+14,'PLANNED',now())
ON CONFLICT(id) DO NOTHING;
INSERT INTO work_item_iteration(id,iteration_id,work_item_id,added_at) VALUES
('dddddddd-0000-0000-0000-000000000011','dddddddd-0000-0000-0000-000000000010','dddddddd-0000-0000-0000-000000000003',now()),
('dddddddd-0000-0000-0000-000000000012','dddddddd-0000-0000-0000-000000000010','dddddddd-0000-0000-0000-000000000004',now())
ON CONFLICT(id) DO NOTHING;
INSERT INTO capacity_entry(iteration_id,external_user_id,available_hours) VALUES
('dddddddd-0000-0000-0000-000000000010','11111111-1111-1111-1111-111111111111',16)
ON CONFLICT(iteration_id,external_user_id) DO NOTHING;
INSERT INTO time_log_entry(id,work_item_id,external_user_id,logged_date,hours,comment,created_at) VALUES
('dddddddd-0000-0000-0000-000000000020','dddddddd-0000-0000-0000-000000000003','11111111-1111-1111-1111-111111111111',current_date,2,'Демо трудозатраты',now())
ON CONFLICT(id) DO NOTHING;
INSERT INTO comment(id,work_item_id,author_external_id,body,created_at) VALUES
('dddddddd-0000-0000-0000-000000000021','dddddddd-0000-0000-0000-000000000003','11111111-1111-1111-1111-111111111111','Демо комментарий',now())
ON CONFLICT(id) DO NOTHING;
COMMIT;
