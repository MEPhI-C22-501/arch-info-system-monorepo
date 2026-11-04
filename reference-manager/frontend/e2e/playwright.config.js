// browser tests of the admin panel against the running local stand: `task up`, then `task tests:e2e`;
// E2E_BASE_URL points at another stand, E2E_CHROMIUM at a Chromium binary already on the machine
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  // the scenarios change the data of the stand, one browser at a time keeps them independent of each other
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  reporter: [['list']],
  outputDir: './test-results',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:8084',
    locale: 'ru-RU',
    timezoneId: 'Europe/Moscow',
    trace: 'retain-on-failure',
    launchOptions: process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
