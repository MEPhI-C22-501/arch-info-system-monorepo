import { test, expect } from '@playwright/test';
test('OIDC login preserves a board deep link and browser navigation',async ({page},testInfo)=>{
  await page.goto('/board');
  await page.locator('#username').fill(process.env.TRACKER_E2E_USER || 'lead');
  await page.locator('#password').fill(process.env.TRACKER_E2E_PASSWORD || 'demo12345');
  await page.locator('#kc-login').click();
  await expect(page.getByRole('heading',{name:'Канбан-доска',exact:true})).toBeVisible();
  await page.screenshot({path:testInfo.outputPath('board.png'),fullPage:true});
  await page.reload();
  await expect(page.getByRole('heading',{name:'Канбан-доска',exact:true})).toBeVisible();
  await page.getByRole('navigation').getByRole('button',{name:'Бэклог'}).click();
  await expect(page).toHaveURL(/\/backlog$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/board$/);
});
test('create a task, discuss it, log time and change status in a batch',async ({page})=>{
  await page.goto('/backlog');
  await page.locator('#username').fill(process.env.TRACKER_E2E_USER || 'lead');
  await page.locator('#password').fill(process.env.TRACKER_E2E_PASSWORD || 'demo12345');
  await page.locator('#kc-login').click();
  await page.getByRole('button',{name:'＋ Создать элемент'}).click();
  const title=`E2E task ${Date.now()}`;
  await page.getByLabel('Название',{exact:true}).fill(title);
  await page.getByLabel('План, ч',{exact:true}).fill('4');
  await page.getByRole('button',{name:'Создать',exact:true}).click();
  await expect(page).toHaveURL(/\/work-items\//);
  const id=new URL(page.url()).pathname.split('/')[2];
  const result=await page.evaluate(async ({id})=>{
    const key=Object.keys(sessionStorage).find(key=>key.startsWith('oidc.user:'))!;
    const token=JSON.parse(sessionStorage.getItem(key)!).access_token;
    const call=async (path:string,body:unknown)=>{
      const response=await fetch(`/api/v1${path}`,{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!response.ok) throw new Error(`${path}: ${response.status}`); return response.json();
    };
    await call(`/work-items/${id}/comments`,{body:'Проверено на демо-стенде'});
    await call(`/work-items/${id}/time-logs`,{hours:1.5,loggedDate:'2026-11-03',comment:'E2E'});
    const response=await fetch(`/api/v1/work-items/${id}`,{headers:{Authorization:`Bearer ${token}`}}); const item=await response.json();
    return call('/work-items/bulk',{operation:'status',value:'00000000-0000-0000-0000-000000000102',items:[{id,version:item.version}]});
  },{id});
  expect(result.results[0].success).toBe(true);
  await page.reload();
  await expect(page.getByText('Проверено на демо-стенде',{exact:true})).toBeVisible();
});
