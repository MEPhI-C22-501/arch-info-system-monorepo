cube('Resources', {
  sql: `SELECT * FROM dwh.cube_resources r WHERE ${FILTER_PARAMS.Resources.day.filter((from,to) => `(r.period_end IS NULL OR r.period_end::date <= ${to}::date)`)}`,
  measures: {
    hours: { sql: `SUM(actual_hours)`, type: 'number', description: 'M-01: logged time' },
    capacityHours: { sql: `SUM(available_hours)`, type: 'number', description: 'Available employee day capacity; unallocated project capacity is unknown' },
    utilizationPercent: { sql: `CASE WHEN MIN(capacity_known)=1 THEN 100.0*SUM(actual_hours)/NULLIF(SUM(available_hours),0) END`, type: 'number', description: 'M-10: missing capacity is null' },
    deficitHours: { sql: `CASE WHEN COUNT(*) FILTER (WHERE id LIKE 'demand:%')=COUNT(required_hours) AND COUNT(required_hours)>0 THEN SUM(required_hours)-COALESCE(SUM(allocated_hours),0) END`, type: 'number', description: 'M-11: demand minus assigned, with separate fact populations' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    day: { sql: `day::date`, type: 'time' },
    role: { sql: `role_code`, type: 'string' },
  },
});
