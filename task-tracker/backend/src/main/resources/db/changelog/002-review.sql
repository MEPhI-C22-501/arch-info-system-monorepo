CREATE TABLE work_item_link (
 id uuid PRIMARY KEY, source_id uuid NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
 target_id uuid NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
 type text NOT NULL CHECK(type IN ('BLOCKS','RELATED')), CHECK(source_id<>target_id),
 UNIQUE(source_id,target_id,type)
);
CREATE INDEX idx_link_target ON work_item_link(target_id);
CREATE TABLE overdue_delivery (
 work_item_id uuid NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
 due_date date NOT NULL, assignee_id text NOT NULL,
 PRIMARY KEY(work_item_id,due_date,assignee_id)
);
CREATE TABLE event_outbox (
 seq bigserial PRIMARY KEY, id uuid NOT NULL UNIQUE, aggregate_id text NOT NULL, payload text NOT NULL,
 state text NOT NULL DEFAULT 'PENDING', attempts integer NOT NULL DEFAULT 0,
 next_attempt timestamptz NOT NULL DEFAULT now(), error text
);
CREATE INDEX idx_outbox_pending ON event_outbox(state,next_attempt);
ALTER TABLE attachment ALTER COLUMN content DROP NOT NULL;
ALTER TABLE attachment ADD COLUMN object_key text;
ALTER TABLE attachment ADD COLUMN sha256 text;
CREATE TABLE object_cleanup (object_key text PRIMARY KEY, after_at timestamptz NOT NULL DEFAULT now()+interval '1 hour');
CREATE FUNCTION queue_attachment_cleanup() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.object_key IS NOT NULL THEN INSERT INTO object_cleanup(object_key,after_at) VALUES(OLD.object_key,now()) ON CONFLICT DO NOTHING; END IF;
 RETURN OLD;
END $$;
CREATE TRIGGER attachment_cleanup AFTER DELETE ON attachment FOR EACH ROW EXECUTE FUNCTION queue_attachment_cleanup();
