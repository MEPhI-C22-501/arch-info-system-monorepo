cube('TestRuns', {
  sql: 'SELECT * FROM dwh.cube_test_runs',
  refreshKey: { every: '1 minute' },
  measures: {
    runsPart: { type: 'count', shown: false },
    passedPart: { sql: `passed`, type: 'sum', shown: false },
    failedPart: { sql: `failed`, type: 'sum', shown: false },
    blockedPart: { sql: `blocked`, type: 'sum', shown: false },
    skippedPart: { sql: `skipped`, type: 'sum', shown: false },
    caseCountPart: { sql: `case_count`, type: 'sum', shown: false },
    caseKnownPart: { sql: `case_count`, type: 'count', shown: false },
    passPercent: { sql: `100.0*${passedPart}/NULLIF(${passedPart}+${failedPart},0)`, type: 'number', description: 'M-14: ratio of sums over runs' },
    executionPercent: { sql: `100.0*(${passedPart}+${failedPart}+${blockedPart}+${skippedPart})/NULLIF(CASE WHEN ${caseKnownPart}=${runsPart} THEN ${caseCountPart} END,0)`, type: 'number', description: 'M-15: ratio of sums; unavailable case count stays null' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    finishedAt: { sql: `finished_at::timestamptz`, type: 'time' },
    runId: { sql: `run_id`, type: 'string' },
  },
  preAggregations: {
    finishedDaily: {
      external: false,
      measures: [runsPart, passedPart, failedPart, blockedPart, skippedPart, caseCountPart, caseKnownPart],
      dimensions: [projectId, userId, runId],
      timeDimension: finishedAt, granularity: 'day',
      refreshKey: { every: '1 minute' },
    },
  },
});
