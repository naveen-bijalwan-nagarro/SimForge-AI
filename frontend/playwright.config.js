import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  outputDir: "../artifacts/browser-tests",
  use: {
    baseURL: process.env.SIMFORGE_TEST_URL || "http://127.0.0.1:8018",
    viewport: { width: 1440, height: 1050 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: process.env.SIMFORGE_BROWSER
      ? { executablePath: process.env.SIMFORGE_BROWSER }
      : {},
  },
});
