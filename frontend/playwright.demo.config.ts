import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testMatch: '**/demo.spec.ts',
  use: { baseURL: 'http://127.0.0.1:4174', ...devices['Desktop Chrome'] },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4174 --strictPort',
    url: 'http://127.0.0.1:4174',
    env: { VITE_ENABLE_DEMO_AUTH: 'true' },
  },
})
