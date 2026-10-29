import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true});
try {
  const page=await browser.newPage();
  await page.goto('http://localhost:8080/');
  await page.locator('#username').fill('planner');
  await page.locator('#password').fill('local-planning-demo');
  await page.locator('#kc-login').click();
  await page.waitForURL('http://localhost:8080/');
  await page.waitForFunction(()=>document.querySelector('#saved')?.textContent.includes('Сохранено на сервере'));
  assert.equal(await page.locator('#role').isVisible(),false);
  console.log('Keycloak browser: Authorization Code + PKCE passed');
} finally {
  await browser.close();
}
