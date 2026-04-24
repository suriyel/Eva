import { defineConfig } from "@playwright/test";

// Playwright 配置 —— 由 ST 阶段使用；TDD Red/Green 不自动执行
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.HARNESS_UI_BASE || "http://127.0.0.1:5173",
  },
  reporter: [["list"]],
});
