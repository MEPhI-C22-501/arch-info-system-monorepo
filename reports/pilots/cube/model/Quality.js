cube('Quality', {
  sql: 'SELECT * FROM dwh.cube_quality',
  refreshKey: { every: '1 minute' },
  measures: {
    defectsPart: { sql: `defect_count`, type: 'sum', shown: false },
    completedPart: { sql: `completed_count`, type: 'sum', shown: false },
    defectDensity: { sql: `CAST(NULL AS numeric)*${defectsPart}`, type: 'number', description: 'M-16: blocked by Q-REP-12; unapproved metric remains null' },
    candidateDefectDensity: { sql: `10.0*${defectsPart}/NULLIF(${completedPart},0)`, type: 'number', description: 'Unapproved candidate per ten completed leaf tasks' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
  },
  preAggregations: {
    byProject: {
      external: false,
      measures: [defectsPart, completedPart],
      dimensions: [projectId, userId],
      refreshKey: { every: '1 minute' },
    },
  },
});
