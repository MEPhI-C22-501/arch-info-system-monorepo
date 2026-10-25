cube('PlanFact', {
  // Separate populations avoid multiplying plans by the number of time logs.
  // period is a marker inside the required window; actual log dates are
  // filtered in SQL, while task plans remain the population at period end.
  sql: `SELECT 'task:'||w.id AS id,w.project_id,w.user_id,
      w.planned_hours,w.remaining_hours,CAST(NULL AS NUMERIC) AS logged_hours,
      ${FILTER_PARAMS.PlanFact.period.filter((from, to) => from)}::date AS period
    FROM dwh.cube_work_items w
    WHERE ${FILTER_PARAMS.PlanFact.period.filter((from, to) => `(w.created_at IS NULL OR w.created_at::timestamptz <= ${to}::timestamptz)`)}
    UNION ALL
    SELECT 'time:'||l.id,l.project_id,l.user_id,NULL,NULL,l.hours_cents/100.0,
      ${FILTER_PARAMS.PlanFact.period.filter((from, to) => from)}::date AS period
    FROM dwh.report_time_log l WHERE ${FILTER_PARAMS.PlanFact.period.filter('l.logged_date::date')}`,
  measures: {
    hours: {sql: 'COALESCE(SUM(logged_hours),0)',type:'number',description:'M-01: period actual hours'},
    plannedHours: {sql:'SUM(planned_hours)',type:'number',description:'M-02: leaf task population at period end'},
    remainingHours: {sql:'SUM(remaining_hours)',type:'number',description:'M-03: source remaining'},
    overrun: {sql:"CASE WHEN COUNT(*) FILTER (WHERE id LIKE 'task:%')=COUNT(planned_hours) AND COUNT(planned_hours)>0 THEN GREATEST(0,COALESCE(SUM(logged_hours),0)-SUM(planned_hours)) END",type:'number',description:'M-04: period hours minus task plan; no join fanout'},
  },
  dimensions: {
    id:{sql:'id',type:'string',primaryKey:true,shown:true},
    userId:{sql:'user_id',type:'string'},projectId:{sql:'project_id',type:'string'},
    period:{sql:'period',type:'time'},
  },
});
