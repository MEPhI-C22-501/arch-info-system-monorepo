cube('TestRuns', {
  sql: 'SELECT * FROM dwh.cube_test_runs',
  measures: {
    passPercent: { sql: `100.0*SUM(passed)/NULLIF(SUM(passed+failed),0)`, type: 'number', description: 'M-14: ratio of sums over runs' },
    executionPercent: { sql: `100.0*SUM(passed+failed+blocked+skipped)/NULLIF(CASE WHEN COUNT(case_count)=COUNT(*) THEN SUM(case_count) END,0)`, type: 'number', description: 'M-15: ratio of sums; unavailable case count stays null' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    finishedAt: { sql: `finished_at::timestamptz`, type: 'time' },
    runId: { sql: `run_id`, type: 'string' },
  },
});
