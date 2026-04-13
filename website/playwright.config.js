import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testMatch: '*.spec.js',
  fullyParallel: false, // workspace has shared server state
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:8199',
    headless: true,
    viewport: { width: 1280, height: 800 },
    actionTimeout: 8000,
    // Don't wait forever — fast failures are useful
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // Dev server must already be running — tests don't start it
  webServer: undefined,
})
