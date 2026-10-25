'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {rewrite}=require('../cube/access');const config=require('../cube/cube');
const claims=(roles,sub='member-1',scope='')=>({sub,scope,resource_access:{reports:{roles}}});
const query=()=>({measures:['TimeLogs.hours']});
const lookup=async()=>({disabled:false,scopes:[{role:'reports-member',employee_id:'member-1',project_id:''}]});
const run=(q,c,state=lookup)=>rewrite(q,{securityContext:c},state);
test('missing malformed and administrator-only roles fail closed',async()=>{
 for(const c of [undefined,{},claims(['unrelated']),claims(['reports-admin']),claims('reports-analyst'),claims(['reports-member',{}]),claims(['reports-member'],''),claims(['reports-member'],'x'.repeat(129))])await assert.rejects(run(query(),c),/scope/);
});
test('member predicate is ANDed with user supplied filters',async()=>{
 const q=await run({...query(),filters:[{member:'TimeLogs.userId',operator:'equals',values:['foreign']}]},claims(['reports-member','reports-admin']));
 assert.deepEqual(q.filters[1],{or:[{member:'TimeLogs.userId',operator:'equals',values:['member-1']}]});
});
test('analyst can read all rows but disabled principals are denied',async()=>{
 assert.deepEqual(await run(query(),claims(['reports-analyst'])),query());
 await assert.rejects(run(query(),claims(['reports-analyst']),async()=>({disabled:true,scopes:[]})),/disabled/);
});
test('project and team scopes apply to every supported model without granting foreign roles',async()=>{
 const state=async()=>({disabled:false,scopes:[{role:'reports-project-manager',project_id:'p-1'},{role:'reports-team-lead',employee_id:'u-2'},{role:'unrelated',project_id:'foreign'}]});
 for(const model of ['WorkItems','Defects','DefectFlow','TestRuns','TestResults','Resources','Forecasts','Quality','StatusFlow']){
 const q=await run({measures:[model+'.records']},claims(['reports-project-manager','reports-team-lead']),state);
 assert.deepEqual(q.filters[0].or.map(f=>f.values),[['p-1'],['u-2']]);
 }
 await assert.rejects(run({measures:['Resources.deficitHours']},claims(['reports-member'])),/scope/);
});
test('money requires cost.read, manager/analyst role and separate currency grouping',async()=>{
 for(const [roles,scope,dimensions]of [[['reports-analyst'],'',[]],[['reports-analyst'],'cost.read',[]],[['reports-team-lead'],'cost.read',['Forecasts.currency']]])await assert.rejects(run({measures:['Forecasts.budgetAdjustment'],dimensions},claims(roles,'a',scope)),/cost/);
 await run({measures:['Forecasts.budgetAdjustment'],dimensions:['Forecasts.currency']},claims(['reports-analyst'],'a','cost.read'));
});
test('BI SQL identity cannot reach new models; mixed cubes are rejected',async()=>{
 assert.deepEqual(await run(query(),claims(['reports-bi-service'])),query());
 await assert.rejects(run({measures:['Forecasts.budgetAdjustment']},claims(['reports-bi-service'])),/scope/);
 await assert.rejects(run({measures:['TimeLogs.hours','WorkItems.plannedHours']},claims(['reports-analyst'])),/scope/);
});
test('unknown SQL identities are denied and production uses the tested rewrite',async()=>{
 assert.equal(config.queryRewrite,rewrite);await assert.rejects(config.checkSqlAuth({},'any-user'),/denied/);
});
