cube('Defects', {
  sql: 'SELECT * FROM dwh.cube_defects',
  measures: {
    opened: { sql: `COUNT(*)`, type: 'number', description: 'M-12: filter createdAt for opened population' },
    remaining: { sql: `CASE WHEN MIN(history_known)=1 THEN SUM(is_open) END`, type: 'number', description: 'M-12: current backlog; incomplete timelines remain null' },
    closeMedian: { sql: `percentile_cont(0.5) WITHIN GROUP (ORDER BY close_days)`, type: 'number', description: 'M-13: first close minus creation; filter firstClosedAt' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    createdAt: { sql: `created_at::timestamptz`, type: 'time' },
    firstClosedAt: { sql: `first_closed_at::timestamptz`, type: 'time' },
    status: { sql: `status_code`, type: 'string' },
  },
});
