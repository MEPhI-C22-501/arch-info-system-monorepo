cube('Defects', {
  sql: 'SELECT * FROM dwh.cube_defects',
  refreshKey: { every: '1 minute' },
  measures: {
    opened: { type: 'count', description: 'M-12: filter createdAt for opened population' },
    openPart: { sql: `is_open`, type: 'sum', shown: false },
    historyKnownPart: { sql: `history_known`, type: 'min', shown: false },
    remaining: { sql: `CASE WHEN ${historyKnownPart}=1 THEN ${openPart} END`, type: 'number', description: 'M-12: current backlog; incomplete timelines remain null' },
    // The median is not additive and is always computed from the facts (ADR-018).
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
  preAggregations: {
    createdDaily: {
      external: false,
      measures: [opened, openPart, historyKnownPart],
      dimensions: [projectId, userId, status],
      timeDimension: createdAt, granularity: 'day',
      refreshKey: { every: '1 minute' },
    },
  },
});
