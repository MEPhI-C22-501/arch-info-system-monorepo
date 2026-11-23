DROP TABLE local_access;

CREATE INDEX idx_outbox_unsent_aggregate ON event_outbox(aggregate_id, seq) WHERE state <> 'SENT';

CREATE OR REPLACE FUNCTION queue_attachment_cleanup() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.object_key IS NOT NULL THEN
    INSERT INTO object_cleanup(object_key,after_at) VALUES(OLD.object_key,now())
      ON CONFLICT (object_key) DO UPDATE SET after_at=LEAST(object_cleanup.after_at,EXCLUDED.after_at);
  END IF;
  RETURN OLD;
END $$;
