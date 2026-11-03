import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  use: { baseURL: process.env.TRACKER_E2E_URL || 'http://localhost:3000', trace: 'retain-on-failure', launchOptions: { executablePath: process.env.TRACKER_CHROME_PATH || undefined } },
  projects: [{name:'desktop',use:{viewport:{width:1280,height:900}}},{name:'mobile',use:{viewport:{width:390,height:844}}}],
});
