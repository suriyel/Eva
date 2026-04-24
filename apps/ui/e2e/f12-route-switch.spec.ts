/**
 * T34 PERF/route-switch——NFR-001 p95 < 500ms
 *
 * Playwright E2E：连续 100 次路由切换 / ↔ /hil，记录每次耗时，取 p95。
 *
 * Red 阶段：此 spec 不会被自动运行（服务未起）；文件以失败态归档，Green + 服务启动后由 ST 阶段运行。
 */
import { test, expect } from "@playwright/test";

const BASE = process.env.HARNESS_UI_BASE || "http://127.0.0.1:5173";

test("T34 路由切换 p95 < 500ms（NFR-001）", async ({ page }) => {
  await page.goto(BASE + "/");
  const samples: number[] = [];
  for (let i = 0; i < 100; i += 1) {
    const start = await page.evaluate(() => performance.now());
    await page.goto(BASE + (i % 2 === 0 ? "/hil" : "/"));
    await page.waitForSelector('[data-component="app-shell"]', { timeout: 5000 });
    const end = await page.evaluate(() => performance.now());
    samples.push(end - start);
  }
  samples.sort((a, b) => a - b);
  const p95 = samples[Math.floor(samples.length * 0.95) - 1];
  expect(p95).toBeLessThan(500);
});
