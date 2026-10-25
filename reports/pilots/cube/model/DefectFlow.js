cube('DefectFlow', {
  sql: 'SELECT * FROM dwh.cube_defect_flow',
  measures: {
    closed: { sql: `COUNT(DISTINCT CASE WHEN to_status='CLOSED' THEN defect_id END)`, type: 'number', description: 'M-12: distinct defects closed during selected period' },
    reopened: { sql: `COUNT(DISTINCT CASE WHEN is_reopen=1 THEN defect_id END)`, type: 'number', description: 'M-17: distinct reopened defects' },
    reopenPercent: { sql: `100.0*COUNT(DISTINCT CASE WHEN is_reopen=1 THEN defect_id END)/NULLIF(COUNT(DISTINCT CASE WHEN to_status='CLOSED' THEN defect_id END),0)`, type: 'number', description: 'M-17: ratio of distinct populations' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    changedAt: { sql: `changed_at::timestamptz`, type: 'time' },
    severity: { sql: `severity`, type: 'string' },
  },
});
