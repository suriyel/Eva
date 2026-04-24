/**
 * PhaseStepper 测试
 *
 * 覆盖：
 *   T21 UI/render · 8 phase + done/current/pending 三态映射
 *   T22 UI/render · current 节点带 data-pulse，animationName='hns-pulse'
 *   T23 UI/render · prefers-reduced-motion:reduce 下 pulse animationName='none'（AC#6）
 *   T28 BNDRY/edge · current=-1 / current=8 抛 RangeError
 */
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { PhaseStepper } from "@/components/phase-stepper";

function mockMatchMedia(reducedMotion: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("prefers-reduced-motion: reduce") ? reducedMotion : false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
    onchange: null,
  })) as unknown as typeof window.matchMedia;
}

describe("PhaseStepper", () => {
  it("T21 current=3 —— 8 phase 节点，0-2 done / 3 current / 4-7 pending", () => {
    mockMatchMedia(false);
    render(<PhaseStepper current={3} />);
    const root = document.querySelector<HTMLElement>('[data-component="phase-stepper"]');
    expect(root).not.toBeNull();
    const phases = root!.querySelectorAll<HTMLElement>("[data-phase-index]");
    expect(phases.length).toBe(8);
    for (let i = 0; i < 8; i += 1) {
      const expected = i < 3 ? "done" : i === 3 ? "current" : "pending";
      expect(phases[i].getAttribute("data-state")).toBe(expected);
    }
  });

  it("T22 current 节点 pulse animationName === 'hns-pulse'（非 reduced-motion）", () => {
    mockMatchMedia(false);
    render(<PhaseStepper current={2} />);
    const pulse = document.querySelector<HTMLElement>(
      '[data-component="phase-stepper"] [data-state="current"] [data-pulse]',
    );
    expect(pulse).not.toBeNull();
    // happy-dom 默认 animationName 空；实现必须显式 style.animationName 或 class 使 getComputedStyle 可读
    const name = getComputedStyle(pulse!).animationName;
    expect(name).toBe("hns-pulse");
  });

  it("T23 prefers-reduced-motion: reduce —— pulse animationName === 'none'（AC#6）", () => {
    mockMatchMedia(true);
    render(<PhaseStepper current={2} />);
    const pulse = document.querySelector<HTMLElement>(
      '[data-component="phase-stepper"] [data-state="current"] [data-pulse]',
    );
    expect(pulse).not.toBeNull();
    expect(getComputedStyle(pulse!).animationName).toBe("none");
  });

  it("T28 current=-1 抛 RangeError", () => {
    mockMatchMedia(false);
    expect(() => render(<PhaseStepper current={-1} />)).toThrow(RangeError);
  });

  it("T28 current=8 抛 RangeError（8 超出 [0,7]）", () => {
    mockMatchMedia(false);
    expect(() => render(<PhaseStepper current={8} />)).toThrow(RangeError);
  });

  // ------------------------------------------------------------------
  // 补充测试：覆盖 fraction 分支（i === current 且 fraction 存在时额外 mono 行）
  // + variant="v" 垂直方向分支 + 边界 current=0 / current=7。
  // Traces To §IC PhaseStepper fraction/variant + §BC current ∈ [0,7] 两端。
  // ------------------------------------------------------------------
  it("fraction 传入 —— 在 current phase 下额外渲染 mono 文本", () => {
    mockMatchMedia(false);
    const { container } = render(<PhaseStepper current={3} fraction="3/8" />);
    // 断言 fraction 文本出现在 current phase 节点内
    const curPhase = container.querySelector<HTMLElement>(
      '[data-phase-index="3"][data-state="current"]',
    );
    expect(curPhase).not.toBeNull();
    expect(curPhase!.textContent).toContain("3/8");
  });

  it("variant='v' —— 外层 flexDirection='column'", () => {
    mockMatchMedia(false);
    const { container } = render(<PhaseStepper current={0} variant="v" />);
    const root = container.querySelector<HTMLElement>('[data-component="phase-stepper"]');
    expect(root).not.toBeNull();
    expect(root!.style.flexDirection).toBe("column");
  });

  it("current=0 —— 仅第 0 项为 current，其余全部 pending（下边界）", () => {
    mockMatchMedia(false);
    const { container } = render(<PhaseStepper current={0} />);
    const phases = container.querySelectorAll<HTMLElement>("[data-phase-index]");
    expect(phases[0].getAttribute("data-state")).toBe("current");
    for (let i = 1; i < phases.length; i += 1) {
      expect(phases[i].getAttribute("data-state")).toBe("pending");
    }
  });

  it("current=7 —— 前 7 项 done，第 7 项 current（上边界）", () => {
    mockMatchMedia(false);
    const { container } = render(<PhaseStepper current={7} />);
    const phases = container.querySelectorAll<HTMLElement>("[data-phase-index]");
    for (let i = 0; i < 7; i += 1) {
      expect(phases[i].getAttribute("data-state")).toBe("done");
    }
    expect(phases[7].getAttribute("data-state")).toBe("current");
  });
});
