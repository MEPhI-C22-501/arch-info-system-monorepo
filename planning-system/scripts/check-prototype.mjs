// npm install --no-save playwright (or set PLAYWRIGHT_MODULE to its module URL).
// Optional MERMAID_BUNDLE points to a local Mermaid browser bundle for diagram QA.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const moduleRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(moduleRoot,'../.doc-tools');fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage(), errors=[];
page.on('pageerror',err=>errors.push(err.message));
await page.goto(pathToFileURL(path.join(moduleRoot,'ui/prototype/index.html')).href);
await page.evaluate(()=>localStorage.clear());await page.reload();
const role=async r=>{await page.locator('#role').selectOption(r)};
const go=async id=>{await page.locator(`nav a[href="#${id}"]`).click();await page.waitForFunction(id=>document.querySelector('nav a[aria-current="page"]')?.getAttribute('href')==='#'+id,id)};
const action=async a=>{await page.locator(`[data-action="${a}"]`).click()};
const value=async()=>page.evaluate(()=>JSON.parse(localStorage.getItem('planning-prototype-v1')));
const fill=async(id,v)=>{await page.locator('#'+id).fill(String(v));await page.locator('#'+id).dispatchEvent('change')};
await go('approval');assert.equal(await page.locator('[data-action="submit"]').isDisabled(),true);
await go('structure');await fill('project-name','Проверка <script> без исполнения');await page.reload();
assert.equal((await value()).name,'Проверка <script> без исполнения');
await role('R-04');await go('resources');await fill('available-hours',6);await action('confirm-resource');
await role('R-02');await go('approval');await action('submit');assert.equal((await value()).status,'ON_REVIEW');
await role('R-01');await go('approval');await fill('return-comment','Уточнить ресурс');await action('return');
assert.equal((await value()).status,'DRAFT');await role('R-02');await action('submit');assert.equal((await value()).reviewRound,2);
await role('R-01');await action('approve');await action('activate');await page.locator('#confirm-yes').click();
assert.equal((await value()).status,'ACTIVE');const baseline=structuredClone((await value()).baseline);
await role('R-02');await go('scenarios');await action('scenario');await fill('scenario-date','2026-10-12');
assert.deepEqual((await value()).baseline,baseline);assert.equal((await value()).version,2);
await role('R-04');await go('resources');await action('confirm-resource');await role('R-02');await go('approval');await action('submit');
await role('R-01');await action('approve');await action('activate');await page.locator('#confirm-yes').click();
assert.equal((await value()).baseline.version,2);
await role('R-06');await go('exchange');await action('retry');assert.equal((await value()).publication,'SUCCEEDED');
assert.equal(await page.locator('nav a').count(),1);
await role('R-05');assert.equal(await page.locator('nav a').count(),2);await go('calendar');
await page.locator('#view-state').selectOption('error');assert.match(await page.locator('#content').innerText(),/Не удалось/);await page.locator('[data-action="normal"]').dispatchEvent('click');assert.equal(await page.locator('#view-state').inputValue(),'normal');
await role('R-02');for(const id of ['portfolio','structure','demand','resources','gantt','conflicts','scenarios','approval','calendar','attachments','forecast']){await go(id);assert.equal(await page.locator('h1').count(),1)}
await go('attachments');await action('attachment');assert.equal((await value()).attachment,true);
await page.locator('#reset').click();await page.locator('#confirm-yes').click();
await page.screenshot({path:path.join(output,'prototype-desktop.png'),fullPage:true});
await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'prototype-mobile.png'),fullPage:true});
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Mobile page overflows');
let diagrams=0;
if(process.env.MERMAID_BUNDLE){
 const diagramPage=await context.newPage();await diagramPage.setContent('<div id="graphs"></div>');await diagramPage.addScriptTag({path:process.env.MERMAID_BUNDLE});
 await diagramPage.evaluate(()=>mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:200000}));
 const docs=path.join(moduleRoot,'docs');
 const sources=[];for(const f of fs.readdirSync(docs).filter(f=>f.endsWith('.md'))){const t=fs.readFileSync(path.join(docs,f),'utf8');for(const [i,m]of [...t.matchAll(/```mermaid\s*\n([\s\S]*?)```/g)].entries())sources.push({name:`${f}:${i+1}`,source:m[1]});}
 for(const f of fs.readdirSync(path.join(docs,'diagrams')).filter(f=>f.endsWith('.mmd')))sources.push({name:f,source:fs.readFileSync(path.join(docs,'diagrams',f),'utf8')});
 for(const [i,s] of sources.entries()){
  const result=await diagramPage.evaluate(async({source,i})=>{try{await mermaid.parse(source);const {svg}=await mermaid.render('d'+i,source);return svg.includes('<svg')?null:'No SVG'}catch(e){return String(e)}},{source:s.source,i});
  if(result)errors.push(`${s.name}: ${result}`);else diagrams++;
 }
}
await browser.close();
console.log(JSON.stringify({prototype:'annual planning, resource conflict, review return, activation, scenario isolation, retry, roles, errors, mobile',diagrams,errors},null,2));
assert.equal(errors.length,0);
