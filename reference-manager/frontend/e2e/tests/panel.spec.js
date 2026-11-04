// scenarios of the admin panel on the demonstration data of `task up`: login, states of the screens, the form,
// roles, the slice at a moment, group operations, the narrow screen and the keyboard (document 115, P-01..P-14)
const { test, expect } = require('@playwright/test');

// users of the local realm, the password equals the login
async function login(page, user, path) {
  await page.goto(path || '/admin/');
  await page.getByLabel('Username or email').fill(user);
  await page.getByLabel('Password', { exact: true }).fill(user);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page.locator('#who')).toContainText(user);
}

test('the root of the panel redirects to /admin/ on the same port', async ({ page, baseURL }) => {
  const response = await page.request.get('/', { maxRedirects: 0 });
  expect(response.status()).toBe(302);
  expect(response.headers().location).toBe('/admin/');

  const bare = await page.request.get('/admin', { maxRedirects: 0 });
  expect(bare.headers().location).toBe('/admin/');

  await page.goto('/');
  await expect(page).toHaveURL(new RegExp(`^(${baseURL}/admin/|http://localhost:8183/)`));
});

test('the files of the panel are revalidated, so a new version never runs with scripts of the old one', async ({ page }) => {
  for (const path of ['/admin/', '/admin/js/app.js', '/admin/js/catalogs.js', '/admin/app.css']) {
    const response = await page.request.get(path);
    expect(response.status(), path).toBe(200);
    expect(response.headers()['cache-control'], path).toBe('no-cache');
    expect(response.headers()['content-security-policy'], `${path} keeps the security headers`).toContain("default-src 'self'");
  }
});

test('the catalog list shows the groups, the counts and an empty search result', async ({ page }) => {
  await login(page, 'hr-admin');
  await expect(page.getByRole('heading', { name: /Кадровые справочники/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Оклады и отсутствия/ })).toBeVisible();
  await expect(page.locator('td[aria-busy="false"]').first()).toBeVisible();

  await page.getByLabel('Поиск справочника').fill('нет такого');
  await expect(page.getByText('Ничего не найдено')).toBeVisible();
  await page.getByLabel('Поиск справочника').fill('Сотр');
  await expect(page.getByRole('link', { name: 'Сотрудники' })).toBeVisible();
});

test('a filtered list, a wrong filter at its field and an empty selection with a reset', async ({ page }) => {
  await login(page, 'hr-admin', '/admin/employees');
  await page.getByLabel('Фильтр').fill('employment_state = "EMPLOYED"');
  await page.getByRole('button', { name: 'Применить' }).click();
  await expect(page).toHaveURL(/filter=employment_state/);
  const rows = page.locator('.table-wrap tbody tr');
  await expect(rows.first()).toBeVisible();
  await expect(page.locator('caption')).toContainText('фильтр employment_state = "EMPLOYED"');
  // dates read as day, month and year
  await expect(rows.first().locator('time').first()).toHaveText(/^\d{2}\.\d{2}\.\d{4}$/);

  await page.getByLabel('Фильтр').fill('employment_state =');
  await page.getByRole('button', { name: 'Применить' }).click();
  await expect(page.getByLabel('Фильтр')).toHaveAttribute('aria-invalid', 'true');
  await expect(page.locator('#filterError')).not.toBeEmpty();

  await page.getByLabel('Фильтр').fill('family_name = "Нет такого"');
  await page.getByRole('button', { name: 'Применить' }).click();
  await expect(page.getByRole('heading', { name: 'Ничего не найдено' })).toBeVisible();
  await page.getByRole('link', { name: 'Сбросить отбор' }).click();
  await expect(rows.first()).toBeVisible();
});

test('the form shows the error of the service at its field and takes the focus there', async ({ page }) => {
  const code = `e2e-${Date.now()}`;
  await login(page, 'hr-admin', '/admin/positions/new');
  await expect(page.getByRole('heading', { name: /Новая запись: Должности/ })).toBeVisible();

  await page.getByLabel(/^Код/).fill('Wrong Code');
  await page.getByLabel(/^Наименование/).fill('Должность из теста');
  await page.getByRole('button', { name: 'Сохранить' }).click();
  const codeInput = page.getByLabel(/^Код/);
  await expect(codeInput).toHaveAttribute('aria-invalid', 'true');
  await expect(codeInput).toBeFocused();
  await expect(page.locator('#f-code-error')).not.toBeEmpty();

  await codeInput.fill(code);
  await page.getByRole('button', { name: 'Сохранить' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Создана запись' })).toBeVisible();
  await expect(page.getByRole('heading', { name: new RegExp(code) })).toBeVisible();
});

test('a reader sees records read only, a user without roles gets the refusal screen', async ({ page, context }) => {
  await login(page, 'reader', '/admin/positions/1');
  await expect(page.getByRole('note')).toContainText('Только чтение');
  await expect(page.getByRole('button', { name: 'Сохранить' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Удалить' })).toHaveCount(0);

  await page.goto('/admin/salaries');
  await expect(page.getByRole('heading', { name: 'Нет доступа' })).toBeVisible();

  await context.clearCookies();
  await page.evaluate(() => sessionStorage.clear());
  await login(page, 'outsider');
  await expect(page.getByRole('heading', { name: 'Нет доступа' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Выйти и войти/ })).toBeVisible();
});

test('a slice at a moment before the demonstration data is empty and narrows the export', async ({ page }) => {
  await login(page, 'reader', '/admin/positions');
  await page.getByLabel('На момент').fill('2020-01-01T12:00');
  await page.getByRole('button', { name: 'Применить' }).click();
  await expect(page).toHaveURL(/readTime=2020-01-01T/);
  await expect(page.getByText(/Срез на 01\.01\.2020/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ничего не найдено' })).toBeVisible();

  await page.goto('/admin/positions?readTime=2099-01-01T00:00:00.000Z');
  await expect(page.locator('.table-wrap tbody tr').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Выгрузить отобранное в Excel' })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Выгрузить отобранное в Excel' }).click();
  expect((await download).suggestedFilename()).toBe('positions.xlsx');
});

test('a group revision of salaries is planned first and saves nothing', async ({ page }) => {
  await login(page, 'hr-admin', '/admin/org_units/1');
  await expect(page.getByRole('heading', { name: 'Групповые операции подразделения' })).toBeVisible();
  const form = page.locator('#reviseForm');
  await form.getByLabel('Включая вложенные подразделения').check();
  await form.getByLabel('Процент').fill('5');
  await form.getByRole('button', { name: 'Проверить' }).click();
  await expect(form.getByText(/^План: изменится окладов \d+, ничего не сохранено\./)).toBeVisible();
  await expect(form.locator('tbody tr').first()).toBeVisible();
  await expect(form.getByText('после выполнения').first()).toBeVisible();

  await form.getByLabel('Изменение').selectOption('amount');
  await form.getByLabel('Новая сумма').fill('-1');
  await form.getByRole('button', { name: 'Проверить' }).click();
  await expect(form.locator('[data-field="amount"] .error')).not.toBeEmpty();
});

test('a click anywhere on a row opens the record, the controls of the row keep their own clicks', async ({ page }) => {
  await login(page, 'hr-admin', '/admin/employees');
  const row = page.locator('.table-wrap tbody tr').nth(1);
  const familyName = row.locator('td').nth(2);
  const name = (await familyName.textContent()).trim();
  await familyName.click();
  await expect(page).toHaveURL(/\/admin\/employees\/\d+$/);
  await expect(page.getByRole('heading', { level: 2 }).first()).toContainText(name);

  // a reference in the row leads to the referenced record, not to the row
  await page.goto('/admin/employees');
  await page.locator('.table-wrap tbody tr').first().locator('td').nth(6).getByRole('link').click();
  await expect(page).toHaveURL(/\/admin\/org_units\/\d+$/);

  // a row of the catalog list opens the catalog
  await page.goto('/admin/');
  await page.locator('tr', { hasText: '/v1/positions/' }).locator('td').nth(1).click();
  await expect(page).toHaveURL(/\/admin\/positions$/);
});

test('a table is part of the page: no inner scroll box, striped rows, a header under the top bar', async ({ page }) => {
  await login(page, 'hr-admin', '/admin/employees');
  const wrap = page.locator('.table-wrap');
  await expect(wrap.locator('tbody tr').first()).toBeVisible();
  const box = await wrap.evaluate((node) => {
    const style = getComputedStyle(node);
    return { maxHeight: style.maxHeight, overflowY: style.overflowY, inner: node.scrollHeight - node.clientHeight, wide: node.scrollWidth - node.clientWidth };
  });
  expect(box).toEqual({ maxHeight: 'none', overflowY: 'visible', inner: 0, wide: 0 });

  // short values never break inside: a date and a state badge take one line each
  const lines = await wrap.locator('tbody tr').first().evaluate((row) => ({
    date: row.querySelector('time').getClientRects().length,
    badge: row.querySelector('.badge').getClientRects().length,
  }));
  expect(lines).toEqual({ date: 1, badge: 1 });
  await expect(wrap.locator('thead th', { hasText: 'Удалена' })).toHaveCount(0);

  // a reference cell names the record shortly and keeps the full label in the tooltip
  const unit = wrap.locator('tbody tr').first().locator('td').nth(6).getByRole('link');
  await expect(unit).toHaveText(/^\S.* #\d+$/);
  await expect(unit).toHaveAttribute('title', /\S+ \S+/);

  const [odd, even] = await wrap.locator('tbody tr').evaluateAll((rows) => rows.slice(0, 2).map((row) => getComputedStyle(row).backgroundColor));
  expect(even).toBe('rgb(238, 241, 245)');
  expect(odd).not.toBe(even);

  const topbar = await page.locator('.topbar').evaluate((node) => node.offsetHeight);
  const headerTop = await wrap.locator('thead th').first().evaluate((node) => getComputedStyle(node).top);
  expect(headerTop).toBe(`${topbar}px`);
});

test('on a narrow screen a table becomes cards with the column names', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, 'hr-admin', '/admin/employees');
  const firstRow = page.locator('.table-wrap tbody tr').first();
  await expect(firstRow).toBeVisible();
  expect(await firstRow.evaluate((row) => getComputedStyle(row).display)).toBe('block');
  const label = await firstRow.locator('td').nth(1).evaluate((cell) => getComputedStyle(cell, '::before').content);
  expect(label).toContain('Табельный номер');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test('the keyboard reaches the content first and the theme switches to dark', async ({ page }) => {
  await login(page, 'reader');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Перейти к содержимому' })).toBeFocused();

  await page.getByRole('button', { name: /^Тема:/ }).click();
  await page.getByRole('button', { name: /^Тема:/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(background).toBe('rgb(15, 20, 27)');
});
