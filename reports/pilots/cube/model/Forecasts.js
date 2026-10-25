cube('Forecasts', {
  sql: 'SELECT * FROM dwh.cube_forecasts',
  measures: {
    budgetAdjustment: { sql: `SUM(budget_adjustment)`, type: 'number', description: 'M-09: Planning source value; cost.read and currency dimension mandatory' },
    estimatedTotalCost: { sql: `SUM(estimated_total_cost)`, type: 'number', description: 'Planning cost; no inferred rates' },
    forecastFinish: { sql: `forecast_finish::timestamptz`, type: 'max', description: 'M-08: latest Planning forecast per project; missing input stays null' },
  },
  dimensions: {
    id: { sql: `id`, type: 'string', primaryKey: true, shown: true },
    projectId: { sql: `project_id`, type: 'string' },
    userId: { sql: `user_id`, type: 'string' },
    currency: { sql: `currency`, type: 'string' },
    quality: { sql: `quality`, type: 'string' },
    calculatedAt: { sql: `calculated_at::timestamptz`, type: 'time' },
  },
});
