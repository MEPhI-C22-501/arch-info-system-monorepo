cube('Resources', {
  sql: `SELECT * FROM dwh.cube_resources r WHERE ${FILTER_PARAMS.Resources.day.filter((from,to) => `(r.period_end IS NULL OR r.period_end::date <= ${to}::date)`)}`,
  refreshKey: { every: '1 minute' },
  measures: {
    capacityKnownPart: { sql: `capacity_known`, type: 'min', shown: false },
    hours: { sql: `actual_hours`, type: 'sum', description: 'M-01: logged time' },
    capacityHours: { sql: `available_hours`, type: 'sum', description: 'Available employee day capacity; unallocated project capacity is unknown' },
    utilizationPercent: { sql: `CASE WHEN ${capacityKnownPart}=1 THEN 100.0*${hours}/NULLIF(${capacityHours},0) END`, type: 'number', description: 'M-10: missing capacity is null' },
    // A demand counts only when its whole interval lies inside the requested period,
    // which depends on the query and is computed from the facts (ADR-018).
    deficitHours: { sql: `CASE WHEN COUNT(*) FILTER (WHERE id LIKE 'demand:%')=COUNT(required_hours) AND COUNT(required_hours)>0 THEN SUM(required_hours)-COALESCE(SUM(allocated_hours),0) END`, type: 'number', description: 'M-11: demand minus assigned, with separate fact populations' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    day: { sql: `day::date`, type: 'time' },
    role: { sql: `role_code`, type: 'string' },
  },
  preAggregations: {
    // Demand rows carry no hours or capacity, so the period-end condition does not change these sums.
    utilizationDaily: {
      external: false,
      measures: [hours, capacityHours, capacityKnownPart],
      dimensions: [projectId, userId, role],
      timeDimension: day, granularity: 'day',
      refreshKey: { every: '1 minute' },
    },
  },
});
