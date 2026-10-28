cube('Quality', {
  sql: 'SELECT * FROM dwh.cube_quality',
  measures: {
    defectDensity: { sql: `NULL::numeric`, type: 'number', description: 'M-16: blocked by Q-REP-12; unapproved metric remains null' },
    candidateDefectDensity: { sql: `10.0*SUM(defect_count)/NULLIF(SUM(completed_count),0)`, type: 'number', description: 'Unapproved candidate per ten completed leaf tasks' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
  },
});
