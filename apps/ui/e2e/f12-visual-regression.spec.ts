/**
 * T35 / T36 UI/render——pixelmatch < 3% vs prototype（UCD §7 SOP）
 *
 * Red 阶段：spec 存在但不自动运行；Green + Playwright setup + pixelmatch 就绪后 ST 阶段运行。
 */
import { test, expect } from "@playwright/test";

const BASE = process.env.HARNESS_UI_BASE || "http://127.0.0.1:5173";

test("T35 viewport 1280x900 —— 与 prototype artboard pixelmatch < 3%", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(BASE + "/");
  const shot = await page.screenshot();
  expect(shot.length).toBeGreaterThan(0);
  // 实际 pixelmatch 对比由 ST 阶段脚本执行；此处占位
  expect(false, "pixelmatch vs docs/design-bundle/eava2/project/pages/overview-1280.png 尚未实现").toBe(true);
});

test("T36 viewport 1440x840 —— 与 prototype 1440 artboard pixelmatch < 3%", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 840 });
  await page.goto(BASE + "/");
  const shot = await page.screenshot();
  expect(shot.length).toBeGreaterThan(0);
  expect(false, "pixelmatch vs docs/design-bundle/eava2/project/pages/overview-1440.png 尚未实现").toBe(true);
});
