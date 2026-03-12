import { defineConfig } from '@playwright/test'

const defaultProdWebUrl = 'https://nice-hill-0533f2700.2.azurestaticapps.net/'
const configuredBaseUrl =
  process.env.PROD_WEB_BASE_URL?.trim() || defaultProdWebUrl

export default defineConfig({
  testDir: './e2e',
  timeout: 240_000,
  expect: {
    timeout: 20_000,
  },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  use: {
    baseURL: configuredBaseUrl.replace(/\/+$/, ''),
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    permissions: ['microphone'],
  },
  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        launchOptions: {
          args: [
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream',
            '--no-sandbox',
          ],
        },
      },
    },
  ],
})
