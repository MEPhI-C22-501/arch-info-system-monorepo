import { test, expect } from '@playwright/test';

test('attachment storage failure leaves the card usable and allows retry', async ({ page }, testInfo) => {
  const id = 'dddddddd-0000-0000-0000-000000000003';
  await page.route(`**/api/v1/work-items/${id}/attachments`, route => route.fulfill({
    json: [{ id: 'test-file', fileName: 'evidence.txt', contentType: 'text/plain', sizeBytes: 8 }],
  }));
  let available = false;
  await page.route(`**/api/v1/work-items/${id}/attachments/test-file`, route => available
    ? route.fulfill({ contentType: 'text/plain', body: 'Evidence' })
    : route.fulfill({ status: 503, json: { errors: [{ field: 'file', reason: 'storage_unavailable' }] } }));
  await page.goto(`/work-items/${id}`);
  await page.locator('#username').fill(process.env.TRACKER_E2E_USER || 'lead');
  await page.locator('#password').fill(process.env.TRACKER_E2E_PASSWORD || 'demo12345');
  await page.locator('#kc-login').click();
  const card = page.getByRole('dialog', { name: 'Карточка рабочего элемента' });
  await card.getByRole('tab', { name: 'Вложения' }).click();
  await card.getByRole('button', { name: 'Просмотр' }).click();
  await expect(card.getByRole('alert')).toHaveText(/Хранилище вложений временно недоступно/);
  await expect(card.getByRole('heading', { name: 'Демо задача в работе' })).toBeVisible();
  await expect(card.locator('iframe')).toHaveCount(0);
  await card.screenshot({ path: testInfo.outputPath('attachment-unavailable.png') });

  available = true;
  await card.getByRole('button', { name: 'Просмотр' }).click();
  await expect(card.getByRole('alert')).toHaveCount(0);
  await expect(card.locator('iframe[title="evidence.txt"]')).toBeVisible();
});

test('iteration status distribution separates labels, counts and shares without overflow', async ({ page }, testInfo) => {
  let empty = false;
  await page.route(/\/api\/v1\/iterations\/[^/?]+$/, async route => {
    const response = await route.fetch();
    const iteration = await response.json();
    await route.fulfill({ response, json: { ...iteration, statusCounts: empty ? {} : {
      'Бэклог': 1, 'В работе': 2, 'Завершена': 3,
      'Очень длинное название пользовательского статуса для проверки переноса': 1,
    } } });
  });
  await page.goto('/iterations');
  await page.locator('#username').fill(process.env.TRACKER_E2E_USER || 'lead');
  await page.locator('#password').fill(process.env.TRACKER_E2E_PASSWORD || 'demo12345');
  await page.locator('#kc-login').click();
  const panel = page.locator('.iteration-statuses');
  await expect(panel.getByText('Всего: 7')).toBeVisible();
  const rows = panel.getByRole('listitem');
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(2).locator('strong')).toHaveText('3');
  await expect(rows.nth(2).locator('small')).toHaveText('43%');
  await expect(rows.nth(2)).toHaveClass(/completed/);
  const fits = await rows.evaluateAll(elements => elements.every(row => {
    const label = row.querySelector('.status-summary-label > span:first-child')!.getBoundingClientRect();
    const value = row.querySelector('.status-summary-value')!.getBoundingClientRect();
    return label.right <= value.left && row.scrollWidth <= row.clientWidth;
  }));
  expect(fits).toBe(true);
  await panel.screenshot({ path: testInfo.outputPath('iteration-statuses.png') });
  empty = true;
  await page.reload();
  await expect(panel.getByText('В итерации пока нет элементов')).toBeVisible();
  await expect(panel.getByRole('listitem')).toHaveCount(0);
});

test('saved backlog view restores filters and sort on the first page', async ({ page }) => {
  await page.goto('/backlog');
  await page.locator('#username').fill(process.env.TRACKER_E2E_USER || 'lead');
  await page.locator('#password').fill(process.env.TRACKER_E2E_PASSWORD || 'demo12345');
  await page.locator('#kc-login').click();

  const type = page.getByRole('combobox', { name: 'Тип', exact: true });
  const sort = page.getByRole('combobox', { name: 'Сортировка' });
  const view = page.getByRole('combobox', { name: 'Представление' });
  await type.selectOption('TASK');
  await sort.selectOption('priority');
  await page.getByRole('textbox', { name: 'Название представления' }).fill('Задачи по приоритету');
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(view).toHaveValue('Задачи по приоритету');

  await page.goto('/backlog?type=BUG&sort=dueDate&page=3');
  await expect(type).toHaveValue('BUG');
  await Promise.all([
    page.waitForResponse(response => {
      const { pathname, searchParams } = new URL(response.url());
      return pathname === '/api/v1/work-items' && response.ok() && searchParams.get('type') === 'TASK'
        && searchParams.get('sort') === 'priority' && searchParams.getAll('page').join(',') === '1';
    }),
    view.selectOption('Задачи по приоритету'),
  ]);
  await expect(type).toHaveValue('TASK');
  await expect(sort).toHaveValue('priority');
  await expect(view).toHaveValue('Задачи по приоритету');
  await expect(page.getByText(/^Страница 1 из /)).toBeVisible();
});

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
