import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 15_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.READ_ALONG_WEB_URL ?? "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
