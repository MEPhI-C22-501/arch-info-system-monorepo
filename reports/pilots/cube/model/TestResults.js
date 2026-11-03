cube('TestResults', {
  sql: 'SELECT * FROM dwh.cube_test_results',
  refreshKey: { every: '1 minute' },
  measures: {
    passedPart: { sql: `CASE WHEN result='PASSED' THEN 1 ELSE 0 END`, type: 'sum', shown: false },
    decidedPart: { sql: `CASE WHEN result IN ('PASSED','FAILED') THEN 1 ELSE 0 END`, type: 'sum', shown: false },
    passPercent: { sql: `100.0*${passedPart}/NULLIF(${decidedPart},0)`, type: 'number', description: 'M-14: blocked and skipped excluded from denominator' },
    executed: { sql: `CASE WHEN result IN ('PASSED','FAILED','BLOCKED','SKIPPED') THEN 1 ELSE 0 END`, type: 'sum', description: 'M-15 numerator: final current result per run and case' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    recordedAt: { sql: `recorded_at::timestamptz`, type: 'time' },
    runId: { sql: `run_id`, type: 'string' },
    result: { sql: `result`, type: 'string' },
  },
  preAggregations: {
    recordedDaily: {
      external: false,
      measures: [passedPart, decidedPart, executed],
      dimensions: [projectId, userId, runId, result],
      timeDimension: recordedAt, granularity: 'day',
      refreshKey: { every: '1 minute' },
    },
  },
});
