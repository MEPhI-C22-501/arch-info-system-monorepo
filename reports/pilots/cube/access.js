'use strict';
// All authorization SQL targets prepared views; no raw HR or app table grants.
let driver;
async function lookup(subject) {
  if (!driver) { const { PostgresDriver } = require('@cubejs-backend/postgres-driver'); driver = new PostgresDriver({ maxPoolSize: 2 }); }
  const principals = await driver.query('SELECT enabled FROM dwh.cube_principal WHERE subject=$1', [subject]);
  const scopes = await driver.query('SELECT role,project_id,employee_id FROM dwh.cube_scope WHERE subject=$1', [subject]);
  return { disabled: principals.some(p => Number(p.enabled) === 0), scopes };
}
const PM='reports-project-manager', TL='reports-team-lead', QA='reports-qa-lead', AN='reports-analyst', MB='reports-member';
const allowed={ TimeLogs:[PM,TL,MB,AN], PlanFact:[PM,TL,AN], WorkItems:[PM,TL,QA,MB,AN], StatusFlow:[PM,TL,AN],
  Defects:[PM,TL,QA,MB,AN], DefectFlow:[PM,TL,QA,AN], TestRuns:[PM,TL,QA,AN], TestResults:[PM,TL,QA,AN],
  Resources:[PM,TL,AN], Forecasts:[PM,TL,AN], Quality:[PM,TL,QA,AN] };
function members(query) {
  const result=[];
  const walk=v=>{ if (typeof v==='string' && /^[A-Z][A-Za-z]*\.[A-Za-z][A-Za-z0-9]*$/.test(v)) result.push(v);
    else if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')Object.entries(v).forEach(([k,x])=>{walk(k);walk(x);}); };
  walk(query);return result;
}
async function rewrite(query, { securityContext: c }, resolve=lookup) {
  const roles=c?.resource_access?.reports?.roles;
  if(!Array.isArray(roles)||roles.some(r=>typeof r!=='string'))throw Error('Reports scope is malformed');
  const refs=members(query); const cubes=[...new Set(refs.map(x=>x.split('.')[0]))];
  if(cubes.length!==1 || !allowed[cubes[0]])throw Error('Reports scope requires one supported cube');
  const cube=cubes[0];
  if(cube==='PlanFact') {
    const period=(query.timeDimensions||[]).find(t=>t.dimension==='PlanFact.period')?.dateRange;
    if(!Array.isArray(period)||period.length!==2||!period.every(d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}(?:T|$)/.test(d))||Date.parse(period[1])<Date.parse(period[0]))throw Error('PlanFact requires an explicit period scope');
  }
  if(refs.includes('TimeLogs.velocity')) {
    const window=(query.timeDimensions||[]).find(t=>t.dimension==='TimeLogs.loggedDate')?.dateRange;
    if(!Array.isArray(window)||window.length!==2||!window.every(d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}(?:T|$)/.test(d))||Date.parse(window[1].slice(0,10))-Date.parse(window[0].slice(0,10))!==27*86400000)throw Error('Velocity requires an explicit four week scope');
  }
  if(roles.includes('reports-bi-service')) {
    if(cube!=='TimeLogs')throw Error('Reports SQL scope denied');
    return query;
  }
  if(typeof c.sub!=='string'||!c.sub.length||c.sub.length>128)throw Error('Reports scope is missing');
  const accepted=roles.filter(r=>allowed[cube].includes(r));
  if(!accepted.length)throw Error('Reports scope denied');
  if(cube==='WorkItems'&&accepted.every(r=>r===QA)&&refs.some(r=>/\.(actualHours|estimateErrorPercent|correctionCoefficient)/.test(r)))throw Error('Reports labor scope denied');
  if(cube==='WorkItems'&&!accepted.some(r=>[PM,MB,AN].includes(r))&&refs.some(r=>/\.(estimateErrorPercent|correctionCoefficient)/.test(r))&&(query.dimensions||[]).includes('WorkItems.userId'))throw Error('Reports employee evaluation scope denied');
  if(cube==='WorkItems' && accepted.every(r=>r===MB || r===QA) && refs.some(r=>/\.(cycle|lead|throughput|averageWip|overrun)/.test(r)))throw Error('Reports scope denied');
  if(cube==='Forecasts'&&refs.some(r=>/\.(budgetAdjustment|estimatedTotalCost)/.test(r))) {
    if(!accepted.some(r=>r===PM||r===AN)||!String(c.scope||'').split(' ').includes('cost.read')||!(query.dimensions||[]).includes('Forecasts.currency'))throw Error('Reports cost scope denied');
  }
  const state=await resolve(c.sub);
  if(state.disabled)throw Error('Reports scope is disabled');
  if(accepted.includes(AN))return query;
  const predicates=[];
  for(const row of state.scopes) {
    if(!accepted.includes(row.role))continue;
    if(row.project_id)predicates.push({member:cube+'.projectId',operator:'equals',values:[row.project_id]});
    if(row.employee_id && (row.role===TL||row.role===MB))predicates.push({member:cube+'.userId',operator:'equals',values:[row.employee_id]});
  }
  if(!predicates.length)throw Error('Reports scope is missing');
  query.filters=[...(query.filters||[]),{or:predicates}];
  return query;
}
module.exports={rewrite,members};
