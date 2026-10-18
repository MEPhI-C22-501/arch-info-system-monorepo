CREATE OR REPLACE FUNCTION planning_guard_baseline() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.kind = 'plan' AND OLD.data->>'status' IN ('APPROVED','ACTIVE','SUPERSEDED','ARCHIVED') THEN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Approved plan cannot be deleted'; END IF;
    IF (OLD.data - ARRAY['revision','status','dataAsOf']) IS DISTINCT FROM
       (NEW.data - ARRAY['revision','status','dataAsOf']) THEN
      RAISE EXCEPTION 'Approved plan content is immutable';
    END IF;
  END IF;
  RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
CREATE OR REPLACE TRIGGER planning_baseline_immutable
BEFORE UPDATE OR DELETE ON records FOR EACH ROW EXECUTE FUNCTION planning_guard_baseline();

CREATE OR REPLACE FUNCTION planning_guard_audit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Audit is append-only'; END;
$$;
CREATE OR REPLACE TRIGGER planning_audit_append_only
BEFORE UPDATE OR DELETE ON audit FOR EACH ROW EXECUTE FUNCTION planning_guard_audit();
