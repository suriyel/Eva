/**
 * T37 UI/render——chrome-devtools MCP snapshot 含 Sidebar + Top header + 主内容区
 *
 * Red 阶段：spec 归档；实际 take_snapshot 由 ST 阶段 MCP 驱动。
 */
import { test, expect } from "@playwright/test";

const BASE = process.env.HARNESS_UI_BASE || "http://127.0.0.1:5173";

test("T37 / 路径 snapshot 含 Sidebar + TopBar + 主内容区 role", async ({ page }) => {
  await page.goto(BASE + "/");
  const sidebar = await page.$('[data-component="sidebar"]');
  const topBar = await page.$('[data-component="top-bar"]');
  const shell = await page.$('[data-component="app-shell"]');
  expect(sidebar, "Sidebar 可见").not.toBeNull();
  expect(topBar, "TopBar 可见").not.toBeNull();
  expect(shell, "AppShell root 可见").not.toBeNull();
});
