cube('StatusFlow', {
  sql: 'SELECT * FROM dwh.cube_daily_wip',
  measures: {
    averageWip: { sql: `CASE WHEN MIN(history_known)=1 THEN 1.0*SUM(is_working)/NULLIF(COUNT(DISTINCT day),0) END`, type: 'number', description: 'M-19: average daily WIP; filter day including zero WIP days' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    day: { sql: `day::date`, type: 'time' },
  },
});
