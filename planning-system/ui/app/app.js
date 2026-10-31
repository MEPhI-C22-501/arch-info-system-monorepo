
'use strict';
const initial=()=>({name:'ERP · планирование ресурсов',role:'R-02',status:'DRAFT',revision:1,version:1,scenario:false,demand:6,allocation:6,availability:4,confirmed:false,reviewRound:0,baseline:null,publication:'FAILED',events:['Создан демонстрационный черновик'],attachment:false,date:'2026-10-09'});
let state=initial(), token='', authMode='demo', plan=null, projectId='10000000-0000-4000-8000-000000000002', pending=false;
const screens=[['portfolio','Портфель и проекты','01'],['structure','Декомпозиция','02'],['demand','Потребность','03'],['resources','Доступность и назначения','04'],['gantt','Диаграмма Ганта','05'],['conflicts','Конфликты ресурсов','06'],['scenarios','Сравнение сценариев','07'],['approval','Согласование версии','08'],['calendar','Личный календарь','09'],['attachments','Вложения','10'],['forecast','План-факт и прогноз','11'],['exchange','Журнал обмена','12']];
let screen=location.hash.slice(1)||'portfolio', mode='normal',timer;
const $=id=>document.getElementById(id), escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const editable=()=>state.projectStatus!=='ARCHIVED'&&state.status==='DRAFT'&&['R-02','R-03'].includes(state.role);
const roleScreens=()=>state.role==='R-06'?['exchange']:state.role==='R-05'?['calendar','attachments']:state.role==='R-04'?['portfolio','resources','conflicts','gantt','approval','attachments']:screens.map(x=>x[0]).filter(x=>x!=='exchange');
const overload=()=>state.overloadHours??Math.max(state.allocation-state.availability,0), deficit=()=>state.deficitHours??Math.max(state.demand-state.allocation,0);
function save(message){$('saved').textContent='Сохранено на сервере · редакция '+state.revision;if(message)toast(message)}
function toast(text){$('toast').textContent=text;clearTimeout(timer);timer=setTimeout(()=>{$('toast').textContent=''},5500)}
function change(message){state.revision++;state.events.push(message);save(message);render()}
function confirmAction(title,text,fn){$('confirm-title').textContent=title;$('confirm-text').textContent=text;$('confirm').showModal();$('confirm-yes').onclick=()=>{$('confirm').close();fn()};$('confirm-no').onclick=()=>$('confirm').close()}
const link=(id,text)=>`<a href="#${id}">${text}</a>`, button=(action,text,primary=false,disabled=false)=>`<button data-action="${action}" ${primary?'class="primary"':''} ${disabled?'disabled':''}>${text}</button>`;
const badge=()=>`<span class="badge ${state.status==='ACTIVE'?'good':''}">${state.status} · V${state.version}</span>`;
function nav(){const visible=roleScreens();if(!visible.includes(screen))screen=visible[0];$('nav').innerHTML=screens.filter(s=>visible.includes(s[0])).map(([id,title,no])=>`<a href="#${id}" ${screen===id?'aria-current="page"':''}><span style="opacity:.5;margin-right:8px">${no}</span>${title}</a>`).join('');$('role').value=state.role}
function render(){nav();const title=screens.find(s=>s[0]===screen)[1];$('main').innerHTML=`<div class="notice"><strong>Planning System.</strong> Данные сохраняются на сервере. ${authMode==='demo'?'Учебный вход и локальные интеграционные заглушки; переключение ролей разрешено только в этой среде.':'Вход через Keycloak.'}</div><div class="page-top"><div><div class="eyebrow">Портфель ERP / ${escape(state.name)}</div><h1>${title}</h1><span class="muted">Версия ${state.version}${state.scenario?' · сценарий «Что если»':''}</span></div><div>${badge()}<div class="status-line">Редакция ${state.revision}</div></div></div><details class="screen-debug"><summary>Проверка состояний экрана</summary><div class="tools" style="margin-bottom:20px"><label for="view-state">Проверка состояния экрана</label><select id="view-state"><option value="normal">Обычный экран</option><option value="loading">Загрузка</option><option value="empty">Нет данных</option><option value="error">Ошибка</option></select></div></details><div id="project-context"></div><div id="content"></div><footer>Planning System · серверная версия · контракты 110–165.</footer>`;$('view-state').value=mode;$('view-state').onchange=e=>{mode=e.target.value;render()};if(mode!=='normal'){$('content').innerHTML=`<div class="card empty" role="status"><h2>${{loading:'Загрузка данных…',empty:'Пока нет данных',error:'Не удалось загрузить данные'}[mode]}</h2><p>${mode==='loading'?'Подождите завершения запроса. Это демонстрационное состояние.':mode==='empty'?'Данные появятся после создания плана или назначения.':'Последний сохранённый план не изменён. Проверьте соединение и повторите.'}</p>${button('normal',mode==='error'?'Повторить':'Вернуться к данным',true)}</div>`;return}$('content').innerHTML=cards[screen]();bindFields();}
const cards={
 portfolio:()=>`<div class="grid"><div class="card"><div class="eyebrow">Проект в портфеле</div><div class="stat">01</div><span class="muted">ERP · годовой план</span></div><div class="card"><div class="eyebrow">Оценка до завершения</div><div class="stat">8 <small>ч</small></div><span class="muted">Ручная оценка планировщика</span></div><div class="card"><div class="eyebrow">Ресурсный конфликт</div><div class="stat">${overload()} <small>ч</small></div><span class="muted">Перегрузка · 5 октября</span></div></div><div class="card"><h2>Проекты</h2><div class="scroll"><table><thead><tr><th>Проект</th><th>Владелец</th><th>План</th><th>Следующий шаг</th></tr></thead><tbody><tr><td><strong>${escape(state.name)}</strong><br><span class="muted">ERP-A · приоритет 1</span></td><td>Демо-руководитель</td><td>${badge()}</td><td>${link('structure','Открыть структуру →')}</td></tr></tbody></table></div></div><div class="card"><h3>Три демонстрационных маршрута</h3><p>${link('structure','Годовое планирование')} → ${link('resources','Ресурсы')} → ${link('approval','Согласование')}.</p><p>${link('conflicts','Конфликт')} → ресурсный руководитель подтверждает доступность → планировщик отправляет версию.</p><p>${link('scenarios','Сценарий')} → сравнение с baseline → новое согласование.</p></div>`,
 structure:()=>`<div class="card"><h2>Работы проекта</h2>${draftHelp()}<label class="field">Название проекта<input id="project-name" value="${escape(state.name)}" ${editable()?'':'disabled'} maxlength="120"></label><p class="muted">Название черновика сохраняется автоматически. Для изменения утверждённого плана создайте сценарий.</p><div class="scroll"><table><thead><tr><th>Элемент</th><th>Тип</th><th>Срок</th><th>План</th></tr></thead><tbody><tr><td>Релиз ERP 1.0</td><td>RELEASE</td><td>05.10 — ${escape(state.date)}</td><td>${state.demand} ч</td></tr><tr><td>↳ Планирование</td><td>EPIC</td><td>05.10 — ${escape(state.date)}</td><td>${state.demand} ч</td></tr><tr><td>　↳ Интерфейс</td><td>FEATURE</td><td>05.10</td><td>${state.demand} ч</td></tr><tr><td>　↳ Приёмка</td><td>MILESTONE</td><td>${escape(state.date)}</td><td>0 ч</td></tr></tbody></table></div><div class="actions">${link('demand','Далее: потребность →')}</div></div>`,
 demand:()=>`<div class="card"><h2>Потребность по ролям и грейдам</h2><p>Интерфейс · FEATURE · 05.10.2026</p><table><thead><tr><th>Специализация</th><th>Грейд</th><th>Часы</th></tr></thead><tbody><tr><td>Разработчик</td><td>Middle</td><td><label><span class="sr-only">Часы потребности</span><input id="demand-hours" type="number" min="1" max="24" value="${state.demand}" ${editable()?'':'disabled'}></label></td></tr></tbody></table><p class="muted">Оценка задаётся листу. Родитель суммирует листья и не добавляет часы повторно.</p><div class="actions">${link('resources','Далее: доступность и назначения →')}</div></div>`,
 resources:()=>`<div class="grid two"><div class="card"><h2>Доступность · 5 октября</h2><p>Демо-сотрудник · employees/demo-1</p><label class="field">Доступно часов<input id="available-hours" type="number" min="0" max="24" value="${state.availability}" ${state.role==='R-04'?'':'disabled'}></label><p class="muted">В исходном примере: 8 часов нормы − 4 часа отсутствия. Изменение здесь моделирует подтверждённую плановую предпосылку.</p>${button('confirm-resource','Подтвердить доступность и назначение',true,state.role!=='R-04'||state.status!=='DRAFT'||overload()>0||deficit()>0)}<p>${state.confirmed?'<span class="badge good">Подтверждено</span>':'Ожидает ресурсного руководителя'}</p></div><div class="card"><h2>Назначение на работу</h2><label class="field">Назначено часов<input id="allocation-hours" type="number" min="1" max="24" value="${state.allocation}" ${editable()?'':'disabled'}></label><p>Потребность: ${state.demand} ч</p><p>Перегрузка: <strong>${overload()} ч</strong> · дефицит: <strong>${deficit()} ч</strong></p><div class="actions">${link('conflicts','Проверить конфликты →')}</div></div></div>`,
 gantt:()=>'<div class="card">Загрузка диаграммы проекта…</div>',
 conflicts:()=>`<div class="card"><h2>${overload()||deficit()?'Нужно уточнить ресурсы':'Блокирующих конфликтов нет'}</h2><p>${overload()?`Назначено ${state.allocation} ч при доступных ${state.availability} ч: перегрузка ${overload()} ч.`:'Перегрузка: 0 ч.'}</p><p>Дефицит потребности: ${deficit()} ч. ${state.allocation>state.demand?'Есть превышение назначения над потребностью.':''}</p><p>Для демо переключитесь на R-04, установите доступность 6 ч и подтвердите назначение. Затем R-02 отправляет план на согласование.</p><div class="actions">${link('resources','Исправить ресурсы →')} ${link('approval','Перейти к согласованию →')}</div></div>`,
 scenarios:()=>`<div class="grid two"><div class="card"><h2>Действующая baseline</h2><p>${state.baseline?`Версия ${state.baseline.version} · ${state.baseline.demand} ч · веха ${escape(state.baseline.date)}`:'Пока нет. Сначала утвердите и активируйте первоначальный план.'}</p><span class="badge good">Содержимое не редактируется</span></div><div class="card"><h2>Вариант «Что если»</h2><p>Копия сохраняет связь с исходной версией. Изменения не затрагивают baseline.</p>${button('scenario','Создать сценарий',true,!state.baseline||!['R-02','R-03'].includes(state.role)||state.scenario&&state.status==='DRAFT')}<label class="field">Веха сценария<input id="scenario-date" type="date" min="2026-10-05" max="2026-12-31" value="${escape(state.date)}" ${state.scenario&&editable()?'':'disabled'}></label><p>${state.scenario&&state.baseline?`Вариант V${state.version}: ${state.date===state.baseline.date?'срок не изменён':'срок изменён, требуется новое согласование'}`:''}</p>${link('approval','Согласовать вариант →')}</div></div>`,
 approval:()=>`<div class="card"><div class="steps">${['DRAFT','ON_REVIEW','APPROVED','ACTIVE'].map(x=>`<span class="step ${x===state.status?'done':''}">${x}</span>`).join('')}</div><h2 style="margin-top:24px">Решение по версии ${state.version}</h2><p>Раунд ${state.reviewRound} · перегрузка ${overload()} ч · дефицит ${deficit()} ч · ресурсы ${state.confirmed?'подтверждены':'не подтверждены'}.</p><p class="muted">Отправка: R-02/R-03. Финальное решение и активация: R-01. Возврат открывает новый цикл редактирования.</p><div class="actions">${button('submit','Отправить на согласование',true,!editable()||!state.confirmed||overload()>0||deficit()>0||state.allocation>state.demand)}${button('approve','Утвердить',true,state.role!=='R-01'||state.status!=='ON_REVIEW')}${button('return','Вернуть на доработку',false,state.role!=='R-01'||state.status!=='ON_REVIEW')}${button('activate','Активировать',true,state.role!=='R-01'||state.status!=='APPROVED')}</div><label class="field">Комментарий для возврата<input id="return-comment" placeholder="Укажите причину"></label></div>`,
 calendar:()=>`<div class="card"><h2>Мои назначения</h2><p>Демо-сотрудник · рабочая неделя 05–09 октября</p><div class="grid"><div class="card"><h3>Понедельник · 05</h3><div class="stat">${state.baseline?state.baseline.allocation:0} ч</div><p>ERP-A · Интерфейс</p></div><div class="card"><h3>Вторник · 06</h3><div class="stat">0 ч</div><p>Назначений нет</p></div><div class="card"><h3>Оповещения</h3><p>${state.baseline?'Опубликована версия V'+state.baseline.version:'Активного плана ещё нет'}</p></div></div><p class="muted">Показаны назначения активной baseline. Факт работы вводится в Task Tracker.</p></div>`,
 attachments:()=>`<div class="card"><h2>Обоснования проекта</h2><p>Файл загружается на сервер; размер и MIME проверяются.</p>${state.attachment?'<p>Загруженные файлы перечислены ниже.</p>':'<p class="muted">Вложений пока нет.</p>'}<div class="actions">${['R-02','R-03'].includes(state.role)?button('attachment','Загрузить вложение',true):''}</div></div>`,
 forecast:()=>`<div class="grid"><div class="card"><div class="eyebrow">Факт</div><div class="stat">12 ч</div><p>Абсолютный срез Task Tracker </p></div><div class="card"><div class="eyebrow">Остаток ETC</div><div class="stat">8 ч</div><p>Явная оценка планировщика</p></div><div class="card"><div class="eyebrow">Полная трудоёмкость</div><div class="stat">20 ч</div><p>Факт + ETC</p></div></div><div class="card"><h2>Качество прогноза <span class="badge bad">PARTIAL</span></h2><p>Нет подтверждённой ставки. Денежный итог не рассчитан. Арифметический остаток задачи не подменяет оценку будущей работы.</p>${link('scenarios','Создать сценарий по отклонению →')}</div>`,
 exchange:()=>`<div class="card"><h2>Публикация плана · Task Tracker</h2><p>Состояние: <strong>${state.publication}</strong> </p><p>Ключ: ERP-A / версия ${state.baseline?.version||1}. В локальной среде ответ приёмника — заглушка.</p>${button('retry','Повторить доставку',true,state.publication==='SUCCEEDED'||!state.baseline)}<p class="muted">Повтор не меняет baseline и сохраняет ключ. Без активного плана отправка недоступна.</p></div><div class="card"><h2>Журнал действий</h2><div class="timeline">${state.events.slice(-10).map(x=>`<p>${escape(x)}</p>`).join('')}</div></div>`
};
async function api(path,method='GET',body=null,revision=null){
 const headers={Authorization:'Bearer '+token};
 if(method!=='GET'){headers['Idempotency-Key']=crypto.randomUUID();if(revision!==null)headers['If-Match']='"'+revision+'"'}
 if(body!==null && !(body instanceof FormData))headers['Content-Type']='application/json';
 const response=await fetch(path,{method,headers,body:body===null?null:body instanceof FormData?body:JSON.stringify(body)});
 if(!response.ok){const error=await response.json().catch(()=>({message:'Ошибка сервера'}));throw Error(error.message||error.detail||'Ошибка '+response.status)}
 return response.headers.get('content-type')?.includes('json')?response.json():response;
}
async function refresh(){
 const next=await api('/api/v1/workspace?projectId='+encodeURIComponent(projectId));
 state={...initial(),...next};state.identity=await api('/api/v1/me');
 if(['R-01','R-02','R-03'].includes(state.role) && state.versionId)plan=await api('/api/v1/versions/'+state.versionId);else plan=null;
 if(state.role==='R-04'){const rows=await api('/api/v1/availability');state.availabilityRecord=rows.find(x=>x.data.id===state.availabilityId)}
 sessionStorage.setItem('planning-project',projectId);render();save();
}
async function command(fn){
 if(pending)return;pending=true;
 try{await fn();await refresh()}catch(e){toast(e.message);await refresh().catch(()=>{})}finally{pending=false}
}
function draft(){return Object.fromEntries(['name','planningMode','horizonStart','horizonEnd','items','dependencies','demands','allocations'].map(k=>[k,structuredClone(plan[k])]))}
async function saveDraft(next){await api('/api/v1/versions/'+plan.id+'/draft','PUT',next,plan.revision)}
function bindFields(){
 for(const[id,field]of [['demand-hours','demand'],['allocation-hours','allocation'],['available-hours','availability']])if($(id))$(id).onchange=e=>command(async()=>{
  const n=Number(e.target.value);if(!Number.isFinite(n)||n<0||n>24)throw Error('Введите часы 0–24');
  if(field==='availability'){
   const row=state.availabilityRecord;if(!row)throw Error('Нет кадрового входа');
   await api('/api/v1/availability/'+row.data.id,'PUT',{...row.data,nominalHours:n+row.data.absenceHours,availableHours:n},row.revision);
  }else{
   const d=draft();
   if(field==='demand'&&!d.demands.length)throw Error('Сначала создайте потребность');
   if(field==='allocation'&&!d.allocations.length)throw Error('Сначала создайте назначение');
   if(field==='demand'){d.demands[0].hours=n;const item=d.items.find(x=>x.id===d.demands[0].planItemId);item.plannedHours=n;for(const p of d.items.filter(x=>['EPIC','RELEASE'].includes(x.type)))p.plannedHours=n}
   else d.allocations[0].hours=n;
   await saveDraft(d);
  }
 });
 if($('project-name'))$('project-name').onchange=e=>command(()=>api('/api/v1/projects/'+projectId,'PATCH',{name:e.target.value.trim(),goal:'Демонстрация планирования'},state.projectRevision));
 if($('scenario-date'))$('scenario-date').onchange=e=>command(async()=>{const d=draft();for(const x of d.items){if(['MILESTONE','EPIC','RELEASE'].includes(x.type))x.finish=e.target.value;if(x.type==='MILESTONE')x.start=e.target.value}await saveDraft(d)});
 if(screen==='attachments'){
  const content=$('content');content.insertAdjacentHTML('beforeend','<div class="card"><label class="field">Выбрать файл<input type="file" id="upload-file" accept=".txt,.pdf,.png,.jpg"></label><div id="file-list"></div></div>');
  $('file-list').innerHTML=(state.attachments||[]).map(x=>`<p>${escape(x.fileName)} · ${x.sizeBytes} байт <button data-download="${escape(x.id)}">Скачать</button></p>`).join('');
 }
 if(screen==='forecast'){
  $('content').innerHTML=`<div class="grid"><div class="card"><h2>Факт</h2><div class="stat">${state.actualHours??'—'} ч</div></div><div class="card"><h2>Остаток ETC</h2><div class="stat">${state.forecast?.remainingHours??'—'} ч</div></div><div class="card"><h2>Прогноз стоимости</h2><div class="stat">${state.forecast?.estimatedTotalCost??'—'} ${escape(state.forecast?.currencyCode||'')}</div></div></div><div class="card"><h2>${escape(state.forecast?.quality||'Не рассчитан')}</h2><p>${escape((state.forecast?.missingInputs||[]).join(', '))}</p><button data-action="forecast">Пересчитать прогноз</button></div>`;
 }
 if(screen==='calendar' && state.role==='R-05')$('content').innerHTML='<div class="card"><h2>Мои назначения</h2>'+(state.allocations||[]).map(x=>`<p>${escape(x.date)} · ${x.hours} ч · ${escape(x.employeeId)}</p>`).join('')+'</div>';
}
document.addEventListener('click',e=>{
 const download=e.target.closest('[data-download]');if(download){command(async()=>{const response=await api('/api/v1/attachments/'+download.dataset.download+'/content');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='attachment';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});return}
 const button=e.target.closest('[data-action]');if(!button||button.disabled)return;
 const action=button.dataset.action;if(action==='normal'){mode='normal';render();return}
 const execute=()=>command(async()=>{
  const prefix='/api/v1/versions/'+state.versionId;
  if(action==='confirm-resource')await api(prefix+'/confirm-resources','POST',{},state.revision);
  if(action==='submit')await api(prefix+'/submit','POST',{reviewers:[{subject:state.finalApprover,role:'FINAL_APPROVER',resourceScope:[]}]},state.revision);
  if(['approve','return'].includes(action))await api(prefix+'/decisions','POST',{reviewRound:state.reviewRound,contentRevision:state.contentRevision,decision:action==='approve'?'APPROVE':'RETURN',comment:action==='return'?$('return-comment').value.trim():null},state.revision);
  if(action==='activate')await api(prefix+'/activate','POST',{projectRevision:state.projectRevision},state.revision);
  if(action==='scenario')await api('/api/v1/projects/'+projectId+'/versions','POST',{baseVersionId:state.versionId,kind:'SCENARIO',name:'Сценарий «Что если»'});
  if(action==='attachment'){
   const file=$('upload-file')?.files[0];if(!file)throw Error('Выберите файл');
   const data=new FormData();data.set('ownerType','PROJECT');data.set('ownerId',projectId);data.set('file',file);
   await api('/api/v1/attachments','POST',data);
  }
  if(action==='retry')await api('/api/v1/publications/'+state.publicationId+'/retry','POST',{reason:'Повтор из интерфейса'});
  if(action==='forecast')await api(prefix+'/forecasts','POST',{contentRevision:state.contentRevision});
 });
 if(action==='activate')confirmAction('Активировать план?','Утверждённая версия станет действующей.',execute);else execute();
});
$('role').onchange=async e=>{if(authMode!=='demo')return;token='demo-'+e.target.value;await refresh().catch(e=>toast(e.message))};
$('reset').hidden=true;
window.addEventListener('hashchange',()=>{screen=location.hash.slice(1);mode='normal';render();$('main').focus()});
async function start(){
 const config=await (await fetch('/auth/config')).json();authMode=config.mode;
 if(authMode==='demo'){token='demo-R-02';const remembered=sessionStorage.getItem('planning-project');if(remembered){const projects=await api('/api/v1/project-cards');if(projects.items.some(p=>p.id===remembered))projectId=remembered;}await refresh();return}
 $('role').hidden=true;
 const url=new URL(location.href);const code=url.searchParams.get('code');
 if(code){
  if(url.searchParams.get('state')!==sessionStorage.getItem('oidc-state'))throw Error('Неверный state входа');
  const verifier=sessionStorage.getItem('oidc-verifier');sessionStorage.removeItem('oidc-state');sessionStorage.removeItem('oidc-verifier');
  const r=await fetch(config.tokenEndpoint,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',client_id:config.clientId,redirect_uri:location.origin+'/',code,code_verifier:verifier})});
  if(!r.ok)throw Error('Не удалось завершить вход');token=(await r.json()).access_token;history.replaceState({},'',location.origin+'/');
  const me=await api('/api/v1/me');const remembered=sessionStorage.getItem('planning-project');if(me.roles.some(r=>['R-01','R-02','R-03','R-04'].includes(r))){const list=await api('/api/v1/project-cards');projectId=list.items.find(p=>p.id===remembered)?.id||list.items.find(p=>me.projects.includes(p.id))?.id||list.items[0]?.id||projectId;}else if(me.projects.length)projectId=me.projects[0];await refresh();return;
 }
 const bytes=crypto.getRandomValues(new Uint8Array(32));const encode=b=>btoa(String.fromCharCode(...b)).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
 const verifier=encode(bytes),stateId=crypto.randomUUID(),challenge=encode(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))));
 sessionStorage.setItem('oidc-verifier',verifier);sessionStorage.setItem('oidc-state',stateId);
 const login=new URL(config.authorizationEndpoint);login.search=new URLSearchParams({client_id:config.clientId,response_type:'code',scope:'openid',redirect_uri:location.origin+'/',state:stateId,code_challenge:challenge,code_challenge_method:'S256'});
 location.assign(login);
}

async function portfolioScreen(){
 try{
  const params=new URLSearchParams({pageSize:'50'});if(state.projectFilter)params.set('q',state.projectFilter);
  const list=await api('/api/v1/projects?'+params);if(screen!=='portfolio')return;
  const container=document.createElement('div');container.className='card';container.innerHTML=`<h2>Реестр проектов</h2><label class="field">Поиск по названию<input id="project-filter" value="${escape(state.projectFilter||'')}"></label><div class="scroll"><table><thead><tr><th>Код</th><th>Название</th><th>Состояние</th><th></th></tr></thead><tbody>${list.items.map(x=>`<tr><td>${escape(x.code)}</td><td>${escape(x.name)}</td><td>${escape(x.status)}</td><td><button data-project="${x.id}">Открыть</button></td></tr>`).join('')}</tbody></table></div>${list.nextCursor?'<p>Показаны первые 50 проектов. Уточните поиск.</p>':''}<details><summary>Создать проект</summary><label class="field">Код<input id="new-code" maxlength="40"></label><label class="field">Название<input id="new-name" maxlength="120"></label><label class="field">Цель<input id="new-goal" maxlength="500"></label><label class="field">Руководитель проекта<select id="new-manager" disabled><option value="">Загрузка руководителей…</option></select></label><button data-extra="new-project" class="primary">Создать</button></details>`;
  $('content').appendChild(container);
  $('project-filter').onchange=()=>{state.projectFilter=$('project-filter').value;render()};
 }catch(e){toast(e.message)}
}
function structureScreen(){
 if(!plan){$('content').innerHTML='<div class="card"><h2>План ещё не создан</h2>'+(['R-02','R-03'].includes(state.role)?'<button data-extra="first-plan">Создать первый план</button>':'<p>План создаёт планировщик или руководитель проекта.</p>')+'</div>';return;}
 const itemRows=plan.items.map(x=>`<tr><td><input data-item="${x.id}" data-field="name" value="${escape(x.name)}" ${editable()?'':'disabled'} aria-label="Название работы"></td><td>${escape(workTypes[x.type]||x.type)}</td><td><input type="date" data-item="${x.id}" data-field="start" value="${x.start}" ${editable()?'':'disabled'} aria-label="Начало работы"></td><td><input type="date" data-item="${x.id}" data-field="finish" value="${x.finish}" ${editable()?'':'disabled'} aria-label="Окончание работы"></td><td><input type="number" data-item="${x.id}" data-field="plannedHours" value="${x.plannedHours}" ${editable()?'':'disabled'} min="0" step="0.01" aria-label="Плановые часы"></td><td>${editable()?`<button data-remove-item="${x.id}">Удалить</button>`:''}</td></tr>`).join('');
 $('content').innerHTML=`<div class="card"><h2>Работы проекта</h2>${draftHelp()}<label class="field">Название проекта<input id="project-name" value="${escape(state.name)}" ${editable()?'':'disabled'}></label><div class="scroll"><table><thead><tr><th>Работа</th><th>Тип</th><th>Начало</th><th>Окончание</th><th>Часы</th><th></th></tr></thead><tbody>${itemRows}</tbody></table></div>${editable()?`<details open class="add-work"><summary>Добавить работу</summary><label class="field">Название<input id="new-item-name"></label><label class="field">Тип<select id="new-item-type">${['FEATURE','STAGE','EPIC','RELEASE','MILESTONE'].map(x=>'<option value="'+x+'">'+workTypes[x]+'</option>').join('')}</select></label><label class="field">Родитель<select id="new-item-parent"><option value="">Без родителя</option>${plan.items.filter(x=>x.type!=='MILESTONE'&&!plan.demands.some(d=>d.planItemId===x.id)).map(x=>`<option value="${x.id}">${escape(x.name)}</option>`).join('')}</select></label><div class="filter-grid"><label class="field">Начало<input id="new-item-start" type="date" value="${plan.horizonStart}"></label><label class="field">Окончание<input id="new-item-finish" type="date" value="${plan.horizonEnd}"></label></div><button data-extra="new-item" class="primary">Добавить работу</button></details>`:''}<div class="actions">${link('demand','Далее: потребность →')}</div></div>`;
 for(const input of document.querySelectorAll('[data-item]'))input.onchange=()=>command(async()=>{const d=draft();const item=d.items.find(x=>x.id===input.dataset.item);if(['start','finish'].includes(input.dataset.field)){const start=item.type==='MILESTONE'||input.dataset.field==='start'?input.value:item.start;const finish=item.type==='MILESTONE'||input.dataset.field==='finish'?input.value:item.finish;await api('/api/v1/versions/'+plan.id+'/timeline','PATCH',{itemId:item.id,start,finish},plan.revision);return;}item[input.dataset.field]=input.dataset.field==='plannedHours'?Number(input.value):input.value;if(item.type==='MILESTONE'){if(['start','finish'].includes(input.dataset.field)){item.start=input.value;item.finish=input.value;}item.plannedHours=0}await saveDraft(d)});
 $('project-name').onchange=e=>command(()=>api('/api/v1/projects/'+projectId,'PATCH',{name:e.target.value.trim(),goal:state.goal||'Планирование проекта'},state.projectRevision));
 $('content').insertAdjacentHTML('beforeend',dependencyForm());
 if($('new-item-parent'))$('new-item-parent').onchange=()=>{const parent=plan.items.find(x=>x.id===$('new-item-parent').value);$('new-item-start').value=parent?.start||plan.horizonStart;$('new-item-finish').value=parent?.finish||plan.horizonEnd};
 if($('save-horizon'))$('save-horizon').onclick=()=>void command(async()=>{const d=draft();d.horizonStart=$('horizon-start').value;d.horizonEnd=$('horizon-end').value;await saveDraft(d)});
 if($('add-dependency'))$('add-dependency').onclick=()=>void command(async()=>{const d=draft();d.dependencies.push({id:crypto.randomUUID(),predecessorId:$('dependency-from').value,successorId:$('dependency-to').value,type:'FS',lagWorkingDays:Number($('dependency-lag').value)});await saveDraft(d)});
 document.querySelectorAll('[data-remove-dependency]').forEach(b=>b.onclick=()=>void command(async()=>{const d=draft();d.dependencies=d.dependencies.filter(x=>x.id!==b.dataset.removeDependency);await saveDraft(d)}));
}
// Keep the prototype's twelve screens, substituting live records in its cards.
const originalBind=bindFields;
bindFields=function(){
 originalBind();if(screen==='portfolio')void portfolioScreen();if(screen==='structure')structureScreen();
 if(screen==='demand' && plan && !plan.demands.length){
  $('content').innerHTML=`<div class="card"><h2>Потребность</h2><p>Выберите листовую работу и задайте роль, грейд и часы.</p><label class="field">Работа<select id="new-demand-item">${plan.items.filter(x=>x.type!=='MILESTONE'&&!plan.items.some(i=>i.parentItemId===x.id)).map(x=>`<option value="${x.id}">${escape(x.name)}</option>`).join('')}</select></label><label class="field">Специализация<select id="new-demand-role" disabled><option>Загрузка…</option></select></label><label class="field">Грейд<select id="new-demand-grade" disabled><option>Загрузка…</option></select></label><label class="field">Часы<input id="new-demand-hours" type="number" min="0" step="0.01" value="6"></label><button data-extra="new-demand">Добавить потребность</button></div>`;
 }
 if(screen==='resources' && plan && !plan.allocations.length)$('content').insertAdjacentHTML('beforeend','<div class="card"><p>Назначить сотрудника на первую потребность</p><label class="field">HR resource name<input id="new-allocation-employee" value="employees/demo-1"></label><button data-extra="new-allocation">Создать назначение</button></div>');
 if(screen==='forecast' && ['R-02','R-03'].includes(state.role))$('content').insertAdjacentHTML('beforeend','<div class="card"><label class="field">Оценка до завершения, ч<input id="etc-hours" type="number" min="0" step="0.01" value="8"></label><button data-extra="save-etc">Сохранить оценку</button></div>');
};
document.addEventListener('click',e=>{
 const selected=e.target.closest('[data-project]');if(selected){projectId=selected.dataset.project;command(()=>Promise.resolve());return}
 const removed=e.target.closest('[data-remove-item]');if(removed){command(async()=>{const d=draft(),id=removed.dataset.removeItem;if(d.items.some(x=>x.parentItemId===id))throw Error('Сначала удалите дочерние работы');const demands=d.demands.filter(x=>x.planItemId===id).map(x=>x.id);d.items=d.items.filter(x=>x.id!==id);d.dependencies=d.dependencies.filter(x=>x.predecessorId!==id&&x.successorId!==id);d.demands=d.demands.filter(x=>x.planItemId!==id);d.allocations=d.allocations.filter(x=>!demands.includes(x.demandId));await saveDraft(d)});return}
 const extra=e.target.closest('[data-extra]');if(!extra)return;
 command(async()=>{
  if(extra.dataset.extra==='new-project'){
   const created=await api('/api/v1/projects','POST',{portfolioId:state.portfolioId,programId:null,code:$('new-code').value.trim(),name:$('new-name').value.trim(),goal:$('new-goal').value.trim(),managerSubject:$('new-manager').value.trim()});projectId=created.id;
   if(['R-02','R-03'].includes(state.role))await api('/api/v1/projects/'+created.id+'/versions','POST',{baseVersionId:null,kind:'PLAN',name:'Первый план'});
  }
  if(extra.dataset.extra==='first-plan')await api('/api/v1/projects/'+projectId+'/versions','POST',{baseVersionId:null,kind:'PLAN',name:'Первый план'});
  if(extra.dataset.extra==='new-item'){
   const d=draft(),type=$('new-item-type').value,parentId=$('new-item-parent').value||null,parent=d.items.find(x=>x.id===parentId),start=$('new-item-start').value,finish=$('new-item-finish').value;
   if(!start||!finish||start>finish)throw Error('Укажите начало и окончание работы');
   if(parent&&d.demands.some(x=>x.planItemId===parent.id))throw Error('У работы с потребностью не может быть дочерних работ. Выберите другого родителя.');
   d.items.push({id:crypto.randomUUID(),logicalItemId:crypto.randomUUID(),parentItemId:parentId,type,name:$('new-item-name').value.trim(),start:type==='MILESTONE'?finish:start,finish,plannedHours:0});await saveDraft(d);
  }
  if(extra.dataset.extra==='new-demand'){
   const d=draft(),item=d.items.find(x=>x.id===$('new-demand-item').value);if(!item)throw Error('Добавьте листовую работу');
   const h=Number($('new-demand-hours').value);d.demands.push({id:crypto.randomUUID(),planItemId:item.id,roleCode:$('new-demand-role').value.trim(),gradeCode:$('new-demand-grade').value.trim(),periodStart:item.start,periodEnd:item.finish,hours:h});syncWorkHours(d);await saveDraft(d);
  }
  if(extra.dataset.extra==='new-allocation'){
   const d=draft(),dem=d.demands[0];if(!dem)throw Error('Сначала создайте потребность');
   d.allocations.push({id:crypto.randomUUID(),demandId:dem.id,employeeId:$('new-allocation-employee').value.trim(),date:dem.periodStart,hours:dem.hours,status:'PROPOSED'});await saveDraft(d);
  }
  if(extra.dataset.extra==='save-etc')await api('/api/v1/versions/'+state.versionId+'/forecast-inputs','PUT',{etc:Number($('etc-hours').value)});
 });
});

// Project cards and per-work assignments share their filters with server XLSX exports.
const projectFilters={q:'',status:'',dateFrom:'',dateTo:'',employeeId:''};
const assignmentFilters={employeeId:'',status:'',dateFrom:'',dateTo:''};
const projectStatusLabels={DRAFT:'Черновик',ACTIVE:'Активный',ON_HOLD:'Приостановлен',COMPLETED:'Завершён',ARCHIVED:'Архив'};
const assignmentStatusLabels={PROPOSED:'Предложено',CONFIRMED:'Подтверждено',CANCELLED:'Отменено'};
let projectRequest=0,resourceRequest=0;
const query=values=>new URLSearchParams(Object.entries(values).filter(([,v])=>v!==''&&v!==null&&v!==undefined)).toString();
const options=(labels,selected,empty)=>`<option value="">${empty}</option>`+Object.entries(labels).map(([value,label])=>`<option value="${escape(value)}" ${value===selected?'selected':''}>${escape(label)}</option>`).join('');
async function downloadExcel(kind,values){
 try{
  const response=await api('/api/v1/downloads/'+kind+'.xlsx?'+query(values));
  const url=URL.createObjectURL(await response.blob());const anchor=document.createElement('a');
  anchor.href=url;anchor.download=kind==='projects'?'Проекты.xlsx':'Назначения.xlsx';anchor.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Файл Excel сформирован');
 }catch(e){toast(e.message)}
}
const filterDates=(prefix,values)=>`<label class="field">С даты<input id="${prefix}-from" type="date" value="${escape(values.dateFrom)}"></label><label class="field">По дату<input id="${prefix}-to" type="date" value="${escape(values.dateTo)}"></label>`;
cards.portfolio=()=>`<div class="card"><div class="section-heading"><div><h2>Проекты</h2><p class="muted">Общая выгрузка содержит все доступные проекты, работы и сотрудников. «Выгрузить по фильтрам» учитывает выбранного сотрудника и остальные параметры. Выберите хотя бы один фильтр, чтобы появилась кнопка персональной выгрузки.</p></div>${state.role!=='R-04'?'<div class="actions"><button id="export-all-projects" class="primary">Все проекты и сотрудники · Excel</button><button id="export-projects" hidden>Выгрузить по фильтрам · Excel</button></div>':''}</div><div class="filter-grid"><label class="field">Название или код<input id="cards-search" value="${escape(projectFilters.q)}" placeholder="Найти проект"></label><label class="field">Статус проекта<select id="cards-status">${options(projectStatusLabels,projectFilters.status,'Все статусы')}</select></label><label class="field">Сотрудник<select id="cards-employee"><option value="">Все сотрудники</option></select></label>${filterDates('cards',projectFilters)}</div><div class="actions"><button id="cards-apply" class="primary">Применить фильтры</button><button id="cards-reset">Сбросить</button></div><p class="muted">Период: пересечение с горизонтом последней версии плана.</p></div>${['R-01','R-02','R-03'].includes(state.role)?`<details class="card create-project"><summary>Создать проект</summary><div class="filter-grid"><label class="field">Код<input id="new-code" maxlength="40"></label><label class="field">Название<input id="new-name" maxlength="120"></label><label class="field">Цель<input id="new-goal" maxlength="500"></label><label class="field">Руководитель проекта<select id="new-manager" disabled><option value="">Загрузка руководителей…</option></select></label></div><button data-extra="new-project" class="primary">Создать</button></details>`:''}<p id="project-count" class="muted" role="status">Загрузка проектов…</p><div id="project-grid" class="project-groups"></div>`;
portfolioScreen=async function(){
 const request=++projectRequest;
 const syncExportButton=()=>{const button=$('export-projects');if(button)button.hidden=!['cards-search','cards-status','cards-employee','cards-from','cards-to'].some(id=>$(id).value.trim());};
 for(const id of ['cards-search','cards-status','cards-employee','cards-from','cards-to']){ $(id).addEventListener('input',syncExportButton);$(id).addEventListener('change',syncExportButton); }
 syncExportButton();
 const readFilters=()=>{projectFilters.employeeId=$('cards-employee').value;projectFilters.q=$('cards-search').value.trim();projectFilters.status=$('cards-status').value;projectFilters.dateFrom=$('cards-from').value;projectFilters.dateTo=$('cards-to').value;};
 $('cards-apply').onclick=()=>{readFilters();render()};
 $('cards-reset').onclick=()=>{Object.keys(projectFilters).forEach(k=>projectFilters[k]='');render()};
 $('cards-search').onkeydown=e=>{if(e.key==='Enter'){readFilters();render()}};
 if($('export-all-projects'))$('export-all-projects').onclick=()=>void downloadExcel('projects',{});
 if($('export-projects'))$('export-projects').onclick=()=>{readFilters();if(!Object.values(projectFilters).some(Boolean))return;render();void downloadExcel('projects',projectFilters)};
 try{
  const choices=await api('/api/v1/export-options');if(screen!=='portfolio'||request!==projectRequest)return;
  $('cards-employee').innerHTML='<option value="">Все сотрудники</option>'+choices.employees.map(x=>`<option value="${escape(x.id)}" ${x.id===projectFilters.employeeId?'selected':''}>${escape(x.name)}</option>`).join('');
  syncExportButton();
  const list=await api('/api/v1/project-cards?'+query(projectFilters));if(screen!=='portfolio'||request!==projectRequest)return;
  $('project-count').textContent=`Найдено проектов: ${list.total}`;
  $('project-grid').innerHTML=[['active','Активные проекты','Есть действующий план. Изменения готовятся в отдельном черновике или сценарии.',list.items.filter(p=>p.status==='ACTIVE')],['inactive','Неактивные проекты','Черновики, приостановленные, завершённые и архивные проекты. Действия зависят от статуса.',list.items.filter(p=>p.status!=='ACTIVE')]].map(([id,title,hint,projects])=>`<section class="project-group" data-project-group="${id}" aria-labelledby="group-${id}"><div class="group-heading"><h2 id="group-${id}">${title} <span class="group-count">${projects.length}</span></h2><p class="muted">${hint}</p></div><div class="project-grid">${projects.length?projects.map(projectCard).join(''):'<div class="card group-empty">В этой группе нет проектов по выбранным фильтрам.</div>'}</div></section>`).join('');
 }catch(e){if(screen==='portfolio'&&request===projectRequest){$('project-count').textContent='Не удалось загрузить проекты: '+e.message;}}
};
const planStatusNames={DRAFT:'Черновик',ON_REVIEW:'На согласовании',APPROVED:'Утверждён',ACTIVE:'Действующий',SUPERSEDED:'Заменён',ARCHIVED:'Архив'};
function projectCard(p){
 const canPlan=['R-02','R-03'].includes(state.role),resource=state.role==='R-04',archived=p.status==='ARCHIVED';
 const action=(target,label,primary=false)=>`<button data-project="${escape(p.id)}" data-project-screen="${target}" ${primary?'class="primary"':''}>${label}</button>`;
 let hint='',actions='';
 if(archived){hint='Архив: можно просматривать сохранённые работы и сроки. Изменения недоступны.';actions=action(resource?'gantt':'structure','Посмотреть архив',true);}
 else if(p.status==='COMPLETED'){hint='Проект завершён. Здесь можно посмотреть сроки и итоговые данные проекта.';actions=action('gantt','Посмотреть сроки',true)+(resource?'':action('forecast','Посмотреть итоги'));}
 else if(!p.versionNumber){hint=canPlan?'План ещё не создан. Создайте его, затем добавьте работы, потребности и сотрудников.':'План ещё не создан. Его создаёт планировщик или руководитель проекта.';actions=action(resource?'resources':'structure',canPlan?'Создать первый план':'Открыть проект',true);}
 else if(p.planStatus==='DRAFT'){
  hint=p.status==='ACTIVE'?'Проект работает по действующему плану. Отдельный черновик можно уточнить и отправить на согласование.':p.status==='ON_HOLD'?'Проект приостановлен. Можно уточнять черновик; для начала исполнения нужен согласованный действующий план.':'Черновик: добавьте работы, задайте потребности и назначьте сотрудников, затем отправьте план на согласование.';
  actions=action(resource?'resources':'structure',resource?'Ресурсы и назначения':canPlan?'Редактировать черновик':'Посмотреть работы',true)+action('gantt','Открыть Гант')+action('approval',canPlan?'Подготовить согласование':'Посмотреть согласование');
 }else if(p.planStatus==='ON_REVIEW'){
  hint=state.role==='R-01'?'План на согласовании: можно утвердить или вернуть на доработку.':'План на согласовании. Работы доступны для просмотра; редактирование — после возврата на доработку.';
  actions=action('approval',state.role==='R-01'?'Рассмотреть план':'Статус согласования',true)+action('gantt','Посмотреть сроки');
 }else if(p.planStatus==='APPROVED'){
  hint=state.role==='R-01'?'План утверждён. Проверьте его и активируйте в разделе согласования.':'План утверждён. Активацию выполняет руководитель портфеля; сроки можно просмотреть на Ганте.';
  actions=action('approval',state.role==='R-01'?'Перейти к активации':'Посмотреть утверждение',true)+action('gantt','Посмотреть сроки');
 }else{
  hint=p.status==='ACTIVE'?'Действующий план доступен для просмотра. Для изменения работ и сроков создайте отдельный сценарий.':'Можно просмотреть работы и сроки последней версии проекта.';
  actions=action('gantt','Посмотреть Гант',true)+(canPlan&&p.status==='ACTIVE'?action('scenarios','Подготовить сценарий'):'')+(resource?'':action('forecast','План-факт и прогноз'));
 }
 return `<article class="card project-card ${p.id===projectId?'selected-project':''}" data-project-status="${escape(p.status)}"><div class="section-heading"><span class="eyebrow">${escape(p.code)}</span><span class="badge ${p.status==='ACTIVE'?'good':''}">${escape(projectStatusLabels[p.status]||p.status)}</span></div><h2>${escape(p.name)}</h2><p class="project-goal">${escape(p.goal||'Планирование ресурсов проекта')}</p><dl><dt>Последняя версия плана</dt><dd>${p.versionNumber?'V'+p.versionNumber+' · '+escape(planStatusNames[p.planStatus]||p.planStatus):'План ещё не создан'}</dd><dt>Горизонт</dt><dd>${escape(p.start||'—')} — ${escape(p.finish||'—')}</dd></dl><div class="project-next"><h3>Что можно сделать</h3><p>${hint}</p><div class="actions">${actions}</div></div></article>`;
}
cards.resources=()=>'<div class="card" id="assignments-panel" role="status">Загрузка назначений…</div>';
async function assignmentScreen(){
 const captured=projectId,request=++resourceRequest;
 try{
  const [resource,list,projects]=await Promise.all([api('/api/v1/resource-options?projectId='+encodeURIComponent(captured)),api('/api/v1/assignments?'+query({projectId:captured,...assignmentFilters})),api('/api/v1/project-cards')]);
  if(screen!=='resources'||projectId!==captured||request!==resourceRequest)return;
  const employeeOptions=selected=>'<option value="">Выберите сотрудника</option>'+resource.employees.map(x=>`<option value="${escape(x.id)}" ${x.id===selected?'selected':''}>${escape(x.name)} · ${escape(x.id)}</option>`).join('');
  const canAssign=['R-02','R-04'].includes(state.role)&&resource.planStatus==='DRAFT';
  const first=resource.demands[0];
  $('content').innerHTML=`<div class="card"><div class="section-heading"><div><h2>Назначения на работы</h2><p class="muted">Последняя версия каждого проекта. Каждый сотрудник назначается на конкретную потребность и дату.</p></div><button id="export-assignments">Скачать назначения Excel</button></div><label class="field">Проект<select id="assignment-project">${projects.items.map(p=>`<option value="${escape(p.id)}" ${p.id===projectId?'selected':''}>${escape(p.code+' · '+p.name)}</option>`).join('')}</select></label><div class="filter-grid"><label class="field">Сотрудник<select id="filter-employee">${employeeOptions(assignmentFilters.employeeId)}</select></label><label class="field">Статус назначения<select id="filter-assignment-status">${options(assignmentStatusLabels,assignmentFilters.status,'Все статусы')}</select></label>${filterDates('assignments',assignmentFilters)}</div><div class="actions"><button id="assignments-apply" class="primary">Применить фильтры</button><button id="assignments-reset">Сбросить</button></div><p class="muted" id="assignment-count">Найдено назначений: ${list.total}</p><div class="scroll"><table><thead><tr><th>Работа</th><th>Сотрудник</th><th>Дата</th><th>Часы</th><th>Статус</th></tr></thead><tbody>${list.items.length?list.items.map(x=>`<tr><td>${escape(x.workName)}</td><td>${canAssign&&x.status!=='CANCELLED'?`<select data-assignment-employee="${escape(x.id)}" aria-label="Сотрудник для ${escape(x.workName)}">${employeeOptions(x.employeeId)}</select>`:escape(x.employeeName)}</td><td>${escape(x.date)}</td><td>${x.hours}</td><td><span data-assignment-status="${x.status}">${escape(assignmentStatusLabels[x.status])}</span>${canAssign&&x.status!=='CANCELLED'?` <button data-cancel-assignment="${escape(x.id)}">Отменить</button>`:''}</td></tr>`).join(''):'<tr><td colspan="5">Назначений по фильтрам нет</td></tr>'}</tbody></table></div></div>${canAssign?`<div class="card"><h2>Назначить сотрудника на работу</h2>${first?`<div class="filter-grid"><label class="field">Работа / потребность<select id="assignment-demand">${resource.demands.map(d=>`<option value="${escape(d.id)}">${escape(d.workName+' · '+d.roleCode+' / '+d.gradeCode)} · ${d.hours} ч</option>`).join('')}</select></label><label class="field">Сотрудник<select id="assignment-employee">${employeeOptions('')}</select></label><label class="field">Дата<input id="assignment-date" type="date" value="${first.periodStart}" min="${first.periodStart}" max="${first.periodEnd}"></label><label class="field">Часы<input id="assignment-hours" type="number" min="0.01" step="0.01" value="${first.hours}"></label></div><p class="muted">Сотрудники показаны из доступных ресурсов Planning System. Новый ресурс сначала должен появиться в кадровом кэше/доступности.</p><button id="add-assignment" class="primary">Добавить назначение</button>`:'<p>Сначала создайте работу и потребность в разделе «Потребность».</p>'}</div>`:'<div class="card"><p>Добавление назначений доступно планировщику или ресурсному руководителю в черновике. Для утверждённого плана создайте сценарий.</p></div>'}${state.role==='R-04'?'<div class="card"><h2>Доступность и подтверждение ресурсов</h2><div class="filter-grid"><label class="field">Сотрудник<select id="availability-employee">'+employeeOptions(resource.employees[0]?.id||'')+'</select></label><label class="field">Дата<input id="availability-date" type="date" value="'+(first?.periodStart||resource.availability[0]?.data.date||'')+'"></label></div><div id="availability-editor"></div><button id="confirm-all-resources" class="primary" '+(resource.planStatus!=='DRAFT'?'disabled':'')+'>Подтвердить назначения моих сотрудников</button></div>':''}`;
  const readFilters=()=>{assignmentFilters.employeeId=$('filter-employee').value;assignmentFilters.status=$('filter-assignment-status').value;assignmentFilters.dateFrom=$('assignments-from').value;assignmentFilters.dateTo=$('assignments-to').value;};
  $('assignment-project').onchange=e=>{Object.keys(assignmentFilters).forEach(k=>assignmentFilters[k]='');projectId=e.target.value;void command(()=>Promise.resolve())};
  $('assignments-apply').onclick=()=>{readFilters();void assignmentScreen()};
  $('assignments-reset').onclick=()=>{Object.keys(assignmentFilters).forEach(k=>assignmentFilters[k]='');void assignmentScreen()};
  $('export-assignments').onclick=()=>{readFilters();void assignmentScreen();void downloadExcel('assignments',{projectId:captured,...assignmentFilters})};
  const editAssignment=(id,changes)=>void command(async()=>{const row=list.items.find(x=>x.id===id);await api('/api/v1/versions/'+resource.versionId+'/assignments/'+id,'PATCH',{demandId:row.demandId,employeeId:row.employeeId,date:row.date,hours:row.hours,...changes},resource.revision);});
  document.querySelectorAll('[data-assignment-employee]').forEach(select=>select.onchange=()=>editAssignment(select.dataset.assignmentEmployee,{employeeId:select.value}));
  document.querySelectorAll('[data-cancel-assignment]').forEach(button=>button.onclick=()=>editAssignment(button.dataset.cancelAssignment,{status:'CANCELLED'}));
  if($('assignment-demand'))$('assignment-demand').onchange=()=>{const demand=resource.demands.find(d=>d.id===$('assignment-demand').value);$('assignment-date').value=demand.periodStart;$('assignment-date').min=demand.periodStart;$('assignment-date').max=demand.periodEnd;$('assignment-hours').value=demand.hours;};
  if($('add-assignment'))$('add-assignment').onclick=()=>void command(async()=>{
   const employeeId=$('assignment-employee').value;if(!employeeId)throw Error('Выберите сотрудника');
   await api('/api/v1/versions/'+resource.versionId+'/assignments','POST',{demandId:$('assignment-demand').value,employeeId,date:$('assignment-date').value,hours:Number($('assignment-hours').value)},resource.revision);
   toast('Назначение добавлено. Оно ожидает подтверждения ресурсов.');
  });
  if(state.role==='R-04'){
   const availabilityEditor=()=>{const row=resource.availability.find(r=>r.data.employeeId===$('availability-employee').value&&r.data.date===$('availability-date').value);$('availability-editor').innerHTML=row?`<label class="field">Доступно часов<input id="resource-hours" type="number" min="0" max="24" step="0.01" value="${row.data.availableHours}"></label><button id="save-resource-hours">Сохранить доступность</button>`:'<p class="muted">На выбранную дату нет записи доступности. Выберите дату из подготовленного календаря.</p>';if(row)$('save-resource-hours').onclick=()=>void command(()=>api('/api/v1/availability/'+row.data.id,'PUT',{...row.data,availableHours:Number($('resource-hours').value),nominalHours:Number($('resource-hours').value)+row.data.absenceHours},row.revision));};
   $('availability-employee').onchange=availabilityEditor;$('availability-date').onchange=availabilityEditor;availabilityEditor();
   $('confirm-all-resources').onclick=()=>void command(()=>api('/api/v1/versions/'+resource.versionId+'/confirm-resources','POST',{},resource.revision));
  }
 }catch(e){if(screen==='resources'&&request===resourceRequest)$('content').innerHTML='<div class="card"><h2>Не удалось загрузить назначения</h2><p>'+escape(e.message)+'</p><p>При истечении сеанса обновите страницу для повторного входа.</p></div>';}
}
function demandScreen(){
 if(!plan){$('content').innerHTML='<div class="card">Сначала создайте план в разделе «Декомпозиция».</div>';return;}
 const works=Object.fromEntries(plan.items.map(x=>[x.id,x.name]));
 const leaves=plan.items.filter(x=>x.type!=='MILESTONE'&&!plan.items.some(i=>i.parentItemId===x.id));
 $('content').innerHTML=`<div class="card"><h2>Потребность по работам</h2>${draftHelp()}<p class="muted">Выберите, какие специалисты нужны на каждую конечную работу и сколько часов потребуется. Одной работе можно добавить несколько специализаций.</p><div class="scroll"><table><thead><tr><th>Работа</th><th>Специализация</th><th>Грейд</th><th>Период</th><th>Часы</th></tr></thead><tbody>${plan.demands.map(d=>`<tr><td>${escape(works[d.planItemId])}</td><td>${escape(choiceName('specialties',d.roleCode))}</td><td>${escape(choiceName('grades',d.gradeCode))}</td><td>${d.periodStart} — ${d.periodEnd}</td><td><input data-demand-hours="${d.id}" aria-label="Часы потребности ${escape(works[d.planItemId])}" type="number" min="0" step="0.01" value="${d.hours}" ${editable()?'':'disabled'}></td></tr>`).join('')||'<tr><td colspan="5">Потребность ещё не задана</td></tr>'}</tbody></table></div></div>${editable()?`<div class="card"><h2>Добавить потребность на работу</h2><div class="filter-grid"><label class="field">Работа<select id="new-demand-item">${leaves.map(x=>`<option value="${x.id}">${escape(x.name)}</option>`).join('')}</select></label><label class="field">Специализация<select id="new-demand-role" disabled><option>Загрузка…</option></select></label><label class="field">Грейд<select id="new-demand-grade" disabled><option>Загрузка…</option></select></label><label class="field">Часы<input id="new-demand-hours" type="number" min="0" step="0.01" value="6"></label></div><button data-extra="new-demand" class="primary" ${leaves.length?'':'disabled'}>Добавить потребность</button></div>`:''}`;
 document.querySelectorAll('[data-demand-hours]').forEach(input=>input.onchange=()=>void command(async()=>{const d=draft();const demand=d.demands.find(x=>x.id===input.dataset.demandHours);demand.hours=Number(input.value);syncWorkHours(d);await saveDraft(d);}));
}
const bindBeforeCards=bindFields;
bindFields=function(){bindBeforeCards();if(screen==='resources')void assignmentScreen();if(screen==='demand')demandScreen();if(screen==='gantt')ganttScreen();void projectContext();void fillPlanningChoices();};
// Card selection changes the working project, then opens its work structure.
document.addEventListener('click',e=>{if(e.target.closest('[data-project]')){location.hash=e.target.closest('[data-project]').dataset.projectScreen||(state.role==='R-04'?'resources':'structure');}});
function dependencyForm(){
 const names=Object.fromEntries(plan.items.map(x=>[x.id,x.name]));
 return `<div class="card"><h2>Горизонт планирования</h2><p class="muted">Все работы должны находиться внутри этого периода. Сначала расширьте горизонт, если нужны другие даты.</p><div class="filter-grid"><label class="field">Начало периода<input type="date" id="horizon-start" value="${plan.horizonStart}" ${editable()?'':'disabled'}></label><label class="field">Окончание периода<input type="date" id="horizon-end" value="${plan.horizonEnd}" ${editable()?'':'disabled'}></label></div>${editable()?'<button id="save-horizon">Сохранить горизонт</button>':''}</div><div class="card"><h2>Зависимости работ</h2><p class="muted">Следующая работа начинается после завершения предыдущей с учётом рабочих дней. Выходные: суббота и воскресенье.</p>${plan.dependencies.map(d=>`<p>${escape(names[d.predecessorId])} → ${escape(names[d.successorId])} · ${d.lagWorkingDays} раб. дн. ${editable()?`<button data-remove-dependency="${d.id}">Удалить связь</button>`:''}</p>`).join('')||'<p>Зависимостей пока нет.</p>'}${editable()&&plan.items.length>1?`<div class="filter-grid"><label class="field">Предыдущая работа<select id="dependency-from">${plan.items.map(x=>`<option value="${x.id}">${escape(x.name)}</option>`).join('')}</select></label><label class="field">Следующая работа<select id="dependency-to">${plan.items.map(x=>`<option value="${x.id}">${escape(x.name)}</option>`).join('')}</select></label><label class="field">Задержка, рабочих дней<input type="number" id="dependency-lag" min="0" max="365" value="0"></label></div><button id="add-dependency">Добавить связь</button>`:''}</div>`;
}
const workTypes={RELEASE:'Релиз',STAGE:'Этап',EPIC:'Эпик',FEATURE:'Работа',MILESTONE:'Веха'};
let planningChoices=null,contextRequest=0,ganttZoom='week',ganttPixels=null,selectedWork=null;
const choiceName=(kind,id)=>planningChoices?.[kind]?.find(x=>x.id===id)?.name||id;
const draftHelp=()=>editable()?'<p class="muted">Черновик: изменения сохраняются на сервере. Сначала добавьте работы, затем потребность и назначения.</p>':`<div class="notice">${plan?'Эта версия доступна для просмотра. Чтобы изменить утверждённый план, создайте сценарий.':'План ещё не создан.'} ${plan&&['APPROVED','ACTIVE'].includes(plan.status)&&['R-02','R-03'].includes(state.role)?link('scenarios','Создать сценарий →'):''}</div>`;
function syncWorkHours(d){
 const total=id=>{const children=d.items.filter(x=>x.parentItemId===id);const item=d.items.find(x=>x.id===id);item.plannedHours=item.type==='MILESTONE'?0:children.length?children.reduce((n,x)=>n+total(x.id),0):d.demands.filter(x=>x.planItemId===id).reduce((n,x)=>n+x.hours,0);return item.plannedHours;};
 d.items.filter(x=>!x.parentItemId).forEach(x=>total(x.id));
}
async function fillPlanningChoices(){
 const current=screen,pid=projectId;
 if(!['portfolio','demand'].includes(current)||!['R-01','R-02','R-03'].includes(state.role))return;
 try{
  const data=await api('/api/v1/planning-options?portfolioId='+encodeURIComponent(state.portfolioId));
  if(screen!==current||projectId!==pid)return;planningChoices=data;
  for(const [id,kind,defaultValue] of [['new-manager','managers',state.role==='R-03'?state.identity.subject:'demo-R-03'],['new-demand-role','specialties','developer'],['new-demand-grade','grades','middle']]){
   const select=$(id);if(!select)continue;select.innerHTML=data[kind].map(x=>`<option value="${escape(x.id)}">${escape(x.name)}</option>`).join('');
   if(data[kind].some(x=>x.id===defaultValue))select.value=defaultValue;select.disabled=!data[kind].length;
  }
 }catch(e){toast('Не удалось загрузить справочники: '+e.message)}
}
async function projectContext(){
 const target=$('project-context'),request=++contextRequest;
 if(!target||!['structure','demand','gantt','conflicts','scenarios','approval'].includes(screen))return;
 try{
  const projects=await api('/api/v1/project-cards');if(request!==contextRequest||!target.isConnected)return;
  target.innerHTML=`<div class="card project-switch"><label class="field">Текущий проект<select id="working-project">${projects.items.map(x=>`<option value="${escape(x.id)}" ${x.id===projectId?'selected':''}>${escape(x.code+' · '+x.name)}</option>`).join('')}</select></label><p class="muted">Все работы, потребности и сроки ниже относятся к этому проекту.</p></div>`;
  $('working-project').onchange=e=>{projectId=e.target.value;selectedWork=null;void command(async()=>{});};
 }catch(e){toast(e.message)}
}
const dayNumber=value=>Math.floor(Date.parse(value+'T00:00:00Z')/86400000);
const isoDay=value=>new Date(value*86400000).toISOString().slice(0,10);
const shortDate=value=>new Date(value+'T00:00:00Z').toLocaleDateString('ru-RU',{day:'2-digit',month:'2-digit',timeZone:'UTC'});
async function ganttScreen(){
 const pid=projectId;
 $('content').innerHTML='<div class="card">Загрузка сроков проекта…</div>';
 try{
  const v=await api('/api/v1/project-timeline?projectId='+encodeURIComponent(pid));if(screen!=='gantt'||pid!==projectId)return;
  if(!v.items.length){$('content').innerHTML='<div class="card empty"><h2>Работ пока нет</h2><p>Добавьте работы и их даты в декомпозиции — они появятся здесь автоматически.</p>'+link('structure','Добавить работы →')+'</div>';return;}
  const ordered=[];const visit=(parent,depth)=>v.items.filter(x=>x.parentItemId===parent).forEach(x=>{ordered.push({...x,depth});visit(x.id,depth+1)});visit(null,0);
  const first=dayNumber(v.horizonStart),last=dayNumber(v.horizonEnd),days=last-first+1;
  const px=ganttPixels??(ganttZoom==='day'?42:ganttZoom==='week'?16:4),width=Math.max(600,days*px),unit=width/days;
  const x=day=>(day-first)*unit;const labels=[];
  for(let day=first;day<=last;day++){
   const date=new Date(day*86400000),show=ganttZoom==='day'||(ganttZoom==='week'?date.getUTCDay()===1:date.getUTCDate()===1)||day===first;
   if(show)labels.push(`<span class="gantt-date" style="left:${x(day)}px">${shortDate(isoDay(day))}${ganttZoom==='month'?'.'+date.getUTCFullYear():''}</span>`);
  }
  const rowY=id=>ordered.findIndex(i=>i.id===id)*48+24;
  const arrows=v.dependencies.map(dep=>{const a=ordered.find(i=>i.id===dep.predecessorId),b=ordered.find(i=>i.id===dep.successorId);if(!a||!b)return '';const ax=x(dayNumber(a.finish)+1),bx=x(dayNumber(b.start)),ay=rowY(a.id),by=rowY(b.id);return `<path d="M ${ax} ${ay} H ${ax+8} V ${by} H ${bx}" fill="none" stroke="#64748b" stroke-width="1.5" marker-end="url(#arrow)"><title>${escape(a.name+' → '+b.name+'; задержка '+dep.lagWorkingDays+' раб. дн.')}</title></path>`;}).join('');
  const chosen=ordered.find(i=>i.id===selectedWork);
  $('content').innerHTML=`<div class="card"><div class="section-heading"><div><h2>Сроки работ · ${escape(state.name)}</h2><p class="muted">${shortDate(isoDay(first))} — ${shortDate(isoDay(last))} · ${ordered.length} элементов. Перетаскивайте полосу для переноса, тяните за края для изменения длительности.</p></div><label class="field">Масштаб<select id="gantt-zoom"><option value="day">Дни</option><option value="week">Недели</option><option value="month">Месяцы</option></select></label></div><label class="field gantt-range">Масштаб: ${px} пикс./день<input id="gantt-scale-slider" type="range" min="4" max="64" step="1" value="${px}"></label><p class="gantt-legend">Синяя полоса — работа · тёмная — группа работ · ◆ — веха · стрелка — зависимость «окончание → начало»</p><div class="scroll gantt-scroll" tabindex="0" aria-label="Диаграмма сроков с горизонтальной прокруткой"><div class="live-gantt" style="width:${260+width}px"><div class="gantt-heading">Работа</div><div class="gantt-scale" style="width:${width}px">${labels.join('')}</div>${ordered.map(i=>`<div class="gantt-name" style="padding-left:${12+i.depth*16}px" title="${escape(i.name)}">${escape(i.name)}<small>${workTypes[i.type]} · ${i.plannedHours} ч</small></div><div class="gantt-track" style="width:${width}px"><button class="gantt-bar ${i.type==='MILESTONE'?'milestone':ordered.some(c=>c.parentItemId===i.id)?'summary-bar':''}" data-gantt-work="${escape(i.id)}" style="left:${x(dayNumber(i.start))}px;width:${i.type==='MILESTONE'?Math.min(24,unit):Math.max(4,(dayNumber(i.finish)-dayNumber(i.start)+1)*unit)}px" aria-label="${escape(i.name)}: ${i.start} — ${i.finish}" title="${escape(i.name)} · ${i.start} — ${i.finish}">${editable()&&i.type!=='MILESTONE'?'<span class="gantt-handle left" data-resize="start" aria-hidden="true"></span>':''}<span class="gantt-bar-text">${i.type==='MILESTONE'?'◆':escape(i.name)}</span>${editable()&&i.type!=='MILESTONE'?'<span class="gantt-handle right" data-resize="finish" aria-hidden="true"></span>':''}</button></div>`).join('')}<svg class="gantt-links" width="${width}" height="${ordered.length*48}" style="left:260px"><defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#64748b"/></marker></defs>${arrows}</svg></div></div><label class="field gantt-range">Прокрутка по времени<input id="gantt-scroll-slider" type="range" min="0" max="1000" value="0"></label><p class="muted">${editable()?'Изменения сохраняются при отпускании мыши. Зависимые работы, периоды потребностей и даты назначений сдвигаются вместе; назначения требуют нового подтверждения ресурсов.':'Версия доступна только для просмотра. Для изменения активного плана создайте сценарий.'}</p><div id="gantt-drag-status" role="status" aria-live="polite"></div></div>${chosen?`<div class="card"><h2>${escape(chosen.name)}</h2><p>${workTypes[chosen.type]} · ${chosen.plannedHours} ч · ${chosen.start} — ${chosen.finish}</p>${editable()?`<div class="filter-grid"><label class="field">Начало<input id="gantt-start" type="date" value="${chosen.start}"></label><label class="field">Окончание<input id="gantt-finish" type="date" value="${chosen.finish}"></label></div><button class="primary" id="gantt-save">Сохранить сроки</button><p class="muted">Сохранение синхронизирует декомпозицию, потребности, назначения и зависимые работы. Доступность сотрудников не переносится: её нужно подтвердить на новые даты.</p>`:draftHelp()}</div>`:''}`;
  $('gantt-zoom').value=ganttZoom;$('gantt-zoom').onchange=e=>{ganttZoom=e.target.value;ganttPixels=null;void ganttScreen()};
  $('gantt-scale-slider').onchange=e=>{ganttPixels=Number(e.target.value);void ganttScreen()};
  const scroll=document.querySelector('.gantt-scroll'),slider=$('gantt-scroll-slider');
  slider.oninput=()=>{scroll.scrollLeft=(scroll.scrollWidth-scroll.clientWidth)*Number(slider.value)/1000};
  scroll.onscroll=()=>{slider.value=scroll.scrollWidth===scroll.clientWidth?0:Math.round(scroll.scrollLeft/(scroll.scrollWidth-scroll.clientWidth)*1000)};
  bindGanttDragging(v,unit,first);

  if($('gantt-save'))$('gantt-save').onclick=()=>void command(async()=>{await api('/api/v1/versions/'+v.id+'/timeline','PATCH',{itemId:chosen.id,start:$('gantt-start').value,finish:chosen.type==='MILESTONE'?$('gantt-start').value:$('gantt-finish').value},v.revision)});
 }catch(e){if(screen==='gantt'&&pid===projectId)$('content').innerHTML='<div class="card">Не удалось загрузить диаграмму: '+escape(e.message)+'</div>';}
}


function bindGanttDragging(v,unit,first){
 for(const el of document.querySelectorAll('[data-gantt-work]')){
  const item=v.items.find(x=>x.id===el.dataset.ganttWork);let gesture=null,suppressClick=false;
  el.onclick=()=>{if(suppressClick){suppressClick=false;return}selectedWork=item.id;void ganttScreen()};
  if(!editable())continue;
  el.classList.add('draggable');
  el.onpointerdown=e=>{
   if(e.button!==0||pending)return;
   gesture={x:e.clientX,scroll:document.querySelector('.gantt-scroll').scrollLeft,edge:e.target.closest('[data-resize]')?.dataset.resize,start:dayNumber(item.start),finish:dayNumber(item.finish),moved:false};
   el.setPointerCapture(e.pointerId);e.preventDefault();
  };
  el.onpointermove=e=>{
   if(!gesture)return;
   const scroll=document.querySelector('.gantt-scroll');
   const delta=Math.round((e.clientX-gesture.x+scroll.scrollLeft-gesture.scroll)/unit);
   const g=gesture;g.moved=g.moved||Math.abs(e.clientX-g.x)>3;
   let start=g.start+(g.edge==='finish'?0:delta),finish=g.finish+(g.edge==='start'?0:delta);
   if(start>finish){if(g.edge==='start')start=finish;else finish=start;}
   if(item.type==='MILESTONE')finish=start;
   g.nextStart=start;g.nextFinish=finish;
   el.style.left=((start-first)*unit)+'px';el.style.width=(item.type==='MILESTONE'?Math.min(24,unit):Math.max(4,(finish-start+1)*unit))+'px';
   el.classList.add('dragging');$('gantt-drag-status').textContent=item.name+': '+isoDay(start)+' — '+isoDay(finish);
  };
  el.onpointerup=e=>{
   if(!gesture)return;const g=gesture;gesture=null;el.releasePointerCapture(e.pointerId);el.classList.remove('dragging');
   if(!g.moved)return;suppressClick=true;
   if(g.nextStart===g.start&&g.nextFinish===g.finish){void ganttScreen();return;}
   selectedWork=item.id;
   void command(async()=>{await api('/api/v1/versions/'+v.id+'/timeline','PATCH',{itemId:item.id,start:isoDay(g.nextStart),finish:isoDay(g.nextFinish)},v.revision);toast('Сроки синхронизированы. Проверьте доступность ресурсов на новые даты.');});
  };
  el.onpointercancel=()=>{gesture=null;suppressClick=true;void ganttScreen()};
  el.onkeydown=e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key)||pending)return;e.preventDefault();const delta=e.key==='ArrowRight'?1:-1;selectedWork=item.id;void command(()=>api('/api/v1/versions/'+v.id+'/timeline','PATCH',{itemId:item.id,start:isoDay(dayNumber(item.start)+delta),finish:isoDay(dayNumber(item.finish)+delta)},v.revision));};
 }
}

start().catch(e=>{$('main').innerHTML='<div class="card"><h1>Не удалось загрузить рабочее пространство</h1><p>'+escape(e.message)+'</p></div>'});
