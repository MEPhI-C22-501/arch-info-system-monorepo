'use strict';
const $=id=>document.getElementById(id);
const issuer='http://localhost:8180/realms/reports-pilot';
let pendingSnapshot=/^\/snapshots\/([0-9a-f-]{36})$/.exec(location.pathname)?.[1]||null;
let token=null,reportQuery=null,catalog=[],lastResult=null;
const text=(id,value)=>{$(id).textContent=typeof value==='string'?value:JSON.stringify(value,null,2);};
const random=()=>Array.from(crypto.getRandomValues(new Uint8Array(32)),v=>v.toString(16).padStart(2,'0')).join('');
const b64=bytes=>btoa(String.fromCharCode(...bytes)).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');
async function login(){
 const state=random(),verifier=random();sessionStorage.setItem('reports.pkce',JSON.stringify({state,verifier,pendingSnapshot}));
 const challenge=b64(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))));
 const query=new URLSearchParams({client_id:'reports-ui',redirect_uri:location.origin+'/ui/callback',response_type:'code',scope:'openid profile email',state,code_challenge:challenge,code_challenge_method:'S256'});
 location.assign(issuer+'/protocol/openid-connect/auth?'+query);
}
async function api(path,method='GET',body){
 const response=await fetch('/api/v1/'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
 if(!response.ok){if(response.status===401){token=null;$('workspace').hidden=true;$('login').hidden=false;$('logout').hidden=true;}let result;try{result=await response.json();}catch{result={code:'REQUEST_FAILED'};}throw new Error(response.status+': '+result.code);}
 if(response.status===204)return null;
 return response.headers.get('Content-Type').includes('json')?response.json():response.blob();
}
const run=fn=>async event=>{event?.preventDefault();try{await fn();}catch(error){text('status',error.message);}};
function query(){const params={periodFrom:$('from').value,periodTo:$('to').value};for(const [id,key] of [['projects','projectIds'],['employees','employeeIds']]){const values=$(id).value.split(',').map(s=>s.trim()).filter(Boolean);if(values.length)params[key]=values;}return {params,slice:[$('slice').value],compareWithPrevious:$('compare').checked};}
function selected(){return $('report').value;}
function slices(){const def=catalog.find(r=>r.reportId===selected());$('slice').replaceChildren(...def.slices.map(s=>{const option=document.createElement('option');option.value=s;option.textContent=s;return option;}));}
const labels={opened:'Создано',closed:'Закрыто',remaining:'Остаток',cycleMedian:'Цикл, медиана',cycleP85:'Цикл, p85',leadMedian:'Полный срок, медиана',leadP85:'Полный срок, p85',throughput:'Завершено по неделям',averageWip:'Среднее задач в работе',errorPercent:'Отклонение, %',correctionCoefficient:'Коэффициент',eligibleTasks:'Задач с оценкой',quality:'Качество',crossCheckFinish:'Сверочный прогноз',missingInputs:'Недостающие данные',estimatedTotalCost:'Прогноз стоимости',currencyCode:'Валюта'};
const notes={PERIOD_NOT_FINISHED:'Период ещё не завершён: показаны данные, известные на время обновления.',PARTIAL_PLANNING_FORECAST:'Прогноз неполный: часть исходных данных отсутствует.',NO_DATA:'По заданным параметрам данных нет.',Q_REP_12_DENSITY_NOT_APPROVED:'Методика плотности дефектов ещё не согласована.',Q_REP_12:'Методика плотности дефектов ещё не согласована.',INCOMPLETE_DEFECT_TIMELINE:'История дефектов неполная.',INCOMPLETE_TASK_HISTORY:'История задач неполная.',MISSING_CAPACITY:'Нет полной информации о доступных часах.',PARTIAL_PLANNING_PERIOD_NOT_PRORATED:'Плановый интервал загружен не полностью: часы не распределяются произвольно.',MISSING_WORKING_STATUS_MAPPING_OR_HISTORY:'Для времени цикла нужны история и соответствие рабочих статусов.',MISSING_PLANNING_FORECAST:'Прогноз планирования не загружен.'};
function formatted(value){if(value===null||value===undefined)return 'не задано';if(value&&typeof value==='object'&&'label'in value)return value.label;if(Array.isArray(value))return value.map(formatted).join(', ');if(typeof value==='object')return Object.entries(value).map(([k,v])=>(labels[k]||k)+': '+formatted(v)).join('; ');if(typeof value==='number')return new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(value);if(value==='PARTIAL')return 'Неполные данные';if(value==='COMPLETE')return 'Полные данные';if(value==='RATE')return 'Ставка';return String(value);}
function show(result){
 lastResult=result;const table=$('result');table.replaceChildren();const head=document.createElement('tr');
 for(const col of result.columns){const th=document.createElement('th');th.textContent=col.title;th.title=col.formula||'';head.append(th);}table.append(head);
 for(const row of result.rows){const tr=document.createElement('tr');for(const col of result.columns){const td=document.createElement('td');td.textContent=formatted(row[col.key]);tr.append(td);}table.append(tr);}
 text('freshness',result.freshness.map(f=>({ 'task-tracker':'Трекер задач','planning-system':'Планирование','reference-manager':'Справочники','qa-system':'Тестирование'}[f.source]||f.source)+': '+(f.state==='FRESH'?'актуально':'нуждается в обновлении')+' · '+new Date(f.dataAsOf).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})+' (МСК)').join('\n'));
 text('notes',result.notes.map(n=>notes[n]||(n.startsWith('MISSING_MAPPING:')?'Не подтверждено соответствие идентификаторов.':n==='Q-REP-12_DENSITY_NOT_APPROVED'?notes.Q_REP_12_DENSITY_NOT_APPROVED:'Не хватает исходных данных для части показателей.')).join(' '));
 $('totals').replaceChildren();for(const [key,value]of Object.entries(result.totals)){const card=document.createElement('div');card.className='card';const title=document.createElement('span'),number=document.createElement('strong');title.textContent=result.columns.find(c=>c.key===key)?.title||labels[key]||key;number.textContent=formatted(value);card.append(title,number);$('totals').append(card);}
 text('comparison',result.comparison?(result.comparison.delta?'Изменение к предыдущему периоду: '+formatted(result.comparison.delta):'Нет данных для сравнения с предыдущим периодом.'):'');
 $('chart').replaceChildren();const leaf=(value,path=[])=>{if(typeof value==='number'&&Number.isFinite(value))return path;if(value&&typeof value==='object'){for(const [key,v]of Object.entries(value)){const found=leaf(v,[...path,key]);if(found)return found;}}return null;};let nested=[];const metric=result.columns.find(c=>{if(c.type!=='measure')return false;for(const row of result.rows){const found=leaf(row[c.key]);if(found){nested=found;return true;}}return false;});const metricValue=row=>nested.reduce((v,key)=>v?.[key],row[metric?.key]);
 if(metric&&result.rows.length){const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');const rows=result.rows.slice(0,12);svg.setAttribute('viewBox','0 0 480 '+(rows.length*45+20));svg.setAttribute('role','img');svg.setAttribute('aria-label',metric.title);const max=Math.max(1,...rows.map(r=>Math.abs(metricValue(r)||0)));rows.forEach((row,index)=>{const label=document.createElementNS(ns,'text'),bar=document.createElementNS(ns,'rect'),value=document.createElementNS(ns,'text');label.setAttribute('x','8');label.setAttribute('y',String(index*45+18));label.setAttribute('font-size','12');label.textContent=formatted(row[result.columns[0].key]).slice(0,48);const n=metricValue(row)||0,w=Math.abs(n)/max*200;bar.setAttribute('x',String(n<0?230-w:230));bar.setAttribute('y',String(index*45+23));bar.setAttribute('width',String(w));bar.setAttribute('height','12');bar.setAttribute('fill','#245a94');value.setAttribute('x','440');value.setAttribute('y',String(index*45+34));value.setAttribute('font-size','12');value.textContent=formatted(n);svg.append(label,bar,value);});$('chart').append(svg);}
 text('status',result.rows.length?'Отчёт сформирован.':'По заданным параметрам данных нет.');
}
function line(id,label,buttons=[]){const row=document.createElement('div'),span=document.createElement('span');span.textContent=label;row.append(span);for(const [caption,callback]of buttons){const button=document.createElement('button');button.textContent=caption;button.addEventListener('click',run(callback));row.append(button);}$(id).append(row);}
async function download(id,format){const blob=await api('exports/'+id+'/file');const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='report-'+id+'.'+format;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function refresh(){
 for(const id of ['views','exports','subscriptions','notifications'])$(id).replaceChildren();
 const views=await api('views');for(const v of views.items)line('views',v.name,[['Открыть',async()=>{$('report').value=v.reportId;slices();$('from').value=v.query.params.periodFrom;$('to').value=v.query.params.periodTo;$('slice').value=v.query.slice?.[0]||'project';$('projects').value=(v.query.params.projectIds||[]).join(',');$('employees').value=(v.query.params.employeeIds||[]).join(',');$('compare').checked=!!v.query.compareWithPrevious;show(await api('reports/'+v.reportId+'/query','POST',{params:{},viewId:v.viewId}));}],['Удалить',async()=>{await api('views/'+v.viewId,'DELETE');await refresh();}]]);
 const exports=await api('exports');for(const e of exports.items)line('exports',e.reportId+' · '+e.format+' · '+e.status,e.status==='COMPLETED'?[['Скачать',()=>download(e.exportId,e.format)]]:[]);
 const subs=await api('subscriptions');for(const s of subs.items)line('subscriptions',s.reportId+' · '+s.schedule+' · '+s.status,[['Завершить',async()=>{await api('subscriptions/'+s.subscriptionId,'DELETE');await refresh();}],['Доставки',async()=>text('status',await api('subscriptions/'+s.subscriptionId+'/deliveries'))]]);
 const notifications=await api('notifications');for(const n of notifications.items)line('notifications',n.kind+' · '+n.createdAt,[['Прочитано',async()=>{await api('notifications/'+n.notificationId,'PATCH',{read:true});await refresh();}]]);
}
async function start(){
 if(location.pathname.endsWith('/callback')){
  const query=new URLSearchParams(location.search);const saved=JSON.parse(sessionStorage.getItem('reports.pkce')||'null');sessionStorage.removeItem('reports.pkce');history.replaceState({},'','/ui/');
  if(!saved||saved.state!==query.get('state')||!query.get('code'))throw new Error('Не удалось подтвердить вход. Повторите вход.');
  const response=await fetch(issuer+'/protocol/openid-connect/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',client_id:'reports-ui',redirect_uri:location.origin+'/ui/callback',code:query.get('code'),code_verifier:saved.verifier})});
  if(!response.ok)throw new Error('Вход не выполнен.');pendingSnapshot=saved.pendingSnapshot||null;token=(await response.json()).access_token;
 }
 if(!token)return;
 $('login').hidden=true;$('logout').hidden=false;$('workspace').hidden=false;
 catalog=(await api('reports')).items;$('report').replaceChildren(...catalog.map(r=>{const option=document.createElement('option');option.value=r.reportId;option.textContent=r.reportId+' — '+r.name;return option;}));
 if(catalog.length)slices();const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow'}).format(new Date());$('from').value=today.slice(0,7)+'-01';$('to').value=today;
 const payload=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0))));$('recipients').value=payload.sub;
 text('status','Вход выполнен. Доступ определяется сервером для каждого запроса.');await refresh();
 if(pendingSnapshot){const job=await api('exports/'+pendingSnapshot);await download(job.exportId,job.format);pendingSnapshot=null;}
}
$('login').onclick=run(login);$('logout').onclick=()=>{token=null;sessionStorage.removeItem('reports.pkce');location.assign(issuer+'/protocol/openid-connect/logout?'+new URLSearchParams({client_id:'reports-ui',post_logout_redirect_uri:location.origin+'/ui/'}));};$('report').onchange=slices;
$('query').onsubmit=run(async()=>{reportQuery=query();show(await api('reports/'+selected()+'/query','POST',reportQuery));});
for(const fmt of ['csv','xlsx'])$(fmt).onclick=run(async()=>{const job=await api('exports','POST',{reportId:selected(),query:query(),format:fmt});text('status','Задание создано: '+job.status+'. Обновите список выгрузок.');await refresh();});
$('print').onclick=run(async()=>{const blob=await api('reports/'+selected()+'/print','POST',query());const url=URL.createObjectURL(blob);window.open(url,'_blank','noopener');setTimeout(()=>URL.revokeObjectURL(url),60000);});
$('save').onclick=run(async()=>{const name=prompt('Название представления');if(name){await api('views','POST',{reportId:selected(),name,query:query()});await refresh();}});
$('subscribe').onsubmit=run(async()=>{await api('subscriptions','POST',{reportId:selected(),query:query(),schedule:$('schedule').value,format:'csv',recipients:$('recipients').value.split(',').map(s=>s.trim()).filter(Boolean)});await refresh();});
$('refresh').onclick=run(refresh);$('audit').onclick=run(async()=>text('audit-result',await api('audit')));
run(start)();
