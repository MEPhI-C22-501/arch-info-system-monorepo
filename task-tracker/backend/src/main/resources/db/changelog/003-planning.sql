CREATE TABLE planning_publication (
  external_id text PRIMARY KEY,
  work_item_id uuid NOT NULL UNIQUE REFERENCES work_item(id),
  version bigint NOT NULL CHECK (version > 0),
  document jsonb NOT NULL,
  retired boolean NOT NULL DEFAULT false
);
CREATE TABLE planning_binding (
  project_external_id text NOT NULL REFERENCES planning_publication(external_id),
  external_id text NOT NULL,
  work_item_id uuid NOT NULL UNIQUE REFERENCES work_item(id),
  PRIMARY KEY(project_external_id, external_id)
);
CREATE FUNCTION protect_planning_item() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM planning_binding WHERE work_item_id=OLD.id)
     AND current_setting('app.planning_write', true) IS DISTINCT FROM 'true' THEN
    IF TG_OP='DELETE' THEN
      RAISE EXCEPTION 'planning_bound_item' USING ERRCODE='23514';
    END IF;
    IF ROW(NEW.title,NEW.parent_id,NEW.assignee_external_id,NEW.start_date,NEW.due_date,NEW.planned_hours)
       IS DISTINCT FROM ROW(OLD.title,OLD.parent_id,OLD.assignee_external_id,OLD.start_date,OLD.due_date,OLD.planned_hours)
       OR (OLD.type IN ('PROJECT','EPIC') AND ROW(NEW.description,NEW.status_id,NEW.priority_id)
           IS DISTINCT FROM ROW(OLD.description,OLD.status_id,OLD.priority_id)) THEN
      RAISE EXCEPTION 'planning_owned_fields' USING ERRCODE='23514';
    END IF;
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER planning_item_guard BEFORE UPDATE OR DELETE ON work_item
  FOR EACH ROW EXECUTE FUNCTION protect_planning_item();
