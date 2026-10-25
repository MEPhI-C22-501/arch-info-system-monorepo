cube('TimeLogs', {
  sql: 'SELECT id, user_id, project_id, logged_date::date AS logged_date, hours_cents FROM dwh.report_time_log',
  measures: {
    hours: { sql: `${CUBE}.hours_cents / 100.0`, type: 'sum', drillMembers: [id, userId, projectId, loggedDate] },
    velocity: { sql: `${hours} / 4.0`, type: 'number', description: 'M-07: filter loggedDate to exactly the selected four week window' },
    records: { type: 'count', drillMembers: [id, userId, projectId, loggedDate] },
  },
  dimensions: {
    id: { sql: `${CUBE}.id`, type: 'string', primaryKey: true, shown: true },
    userId: { sql: `${CUBE}.user_id`, type: 'string' },
    projectId: { sql: `${CUBE}.project_id`, type: 'string' },
    loggedDate: { sql: `${CUBE}.logged_date`, type: 'time' },
  },
  preAggregations: {
    daily: {
      external: false,
      measures: [hours, records], dimensions: [userId, projectId],
      timeDimension: loggedDate, granularity: 'day',
      refreshKey: { every: '1 minute' },
    },
  },
});
