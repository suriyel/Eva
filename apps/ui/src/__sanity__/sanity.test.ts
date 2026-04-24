/**
 * 测试基础设施 smoke test——本测试不验证任何业务行为，
 * 仅用于证明 Vitest + happy-dom + jest-dom 已就绪。
 *
 * 在 TDD Red 阶段：此测试应 PASS；其余 feature 测试全部 FAIL（模块未实现）。
 * 若本测试 FAIL，意味着测试 harness 本身坏了，必须先修复。
 */
import { describe, it, expect } from "vitest";

describe("vitest harness smoke", () => {
  it("happy-dom DOM 可用", () => {
    const el = document.createElement("div");
    el.setAttribute("data-kind", "sanity");
    expect(el.getAttribute("data-kind")).toBe("sanity");
  });

  it("jest-dom matchers 已挂载", () => {
    const el = document.createElement("span");
    el.textContent = "ok";
    expect(el).toHaveTextContent("ok");
  });
});
