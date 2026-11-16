-- Backfill the new optional field without changing project revision or touching plan baselines.
UPDATE records
SET data = jsonb_set(data, '{hourBudgetCents}', 'null'::jsonb)
WHERE kind = 'project' AND NOT (data ? 'hourBudgetCents');
