/**
 * TicketCard 测试
 *
 * 覆盖：
 *   T24 UI/render · state='running' —— [data-state-dot] 背景 var(--state-running)，含 .pulse 类
 *   T25 UI/render · tool='claude' —— [data-tool='claude'] 渲染，color=#D2A8FF
 *   T27 UI/render · prefers-reduced-motion 下 ticket state-dot.pulse 的伪元素动画 animationName='none'
 */
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { TicketCard } from "@/components/ticket-card";

function mockMatchMedia(reduced: boolean) {
  window.matchMedia = vi.fn().mockImplementation((q: string) => ({
    matches: q.includes("prefers-reduced-motion: reduce") ? reduced : false,
    media: q,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
    onchange: null,
  })) as unknown as typeof window.matchMedia;
}

describe("TicketCard", () => {
  it("T24 state='running' —— state-dot 含 pulse 类，背景色绑 --state-running token", () => {
    mockMatchMedia(false);
    render(
      <TicketCard id="t-1" state="running" status="执行中" skill="coder" tool="claude" />,
    );
    const dot = document.querySelector<HTMLElement>(
      '[data-component="ticket-card"] [data-state-dot]',
    );
    expect(dot).not.toBeNull();
    expect(dot!.classList.contains("pulse")).toBe(true);
    const bg = getComputedStyle(dot!).backgroundColor;
    // 实现可能用内联 style="background-color: var(--state-running)"；happy-dom 下应返回该字符串
    expect(bg.includes("var(--state-running)") || bg === "rgb(62, 207, 142)").toBe(true);
  });

  it("T25 tool='claude' —— [data-tool='claude'] 存在，color=#D2A8FF", () => {
    mockMatchMedia(false);
    render(
      <TicketCard id="t-2" state="running" status="..." skill="coder" tool="claude" />,
    );
    const chip = document.querySelector<HTMLElement>(
      '[data-component="ticket-card"] [data-tool="claude"]',
    );
    expect(chip).not.toBeNull();
    const color = getComputedStyle(chip!).color.toLowerCase();
    expect(
      color === "rgb(210, 168, 255)" || color === "#d2a8ff",
    ).toBe(true);
  });

  it("T27 prefers-reduced-motion —— ticket-card state-dot.pulse 的动画被禁用", () => {
    mockMatchMedia(true);
    render(
      <TicketCard id="t-3" state="running" status="..." skill="coder" tool="claude" />,
    );
    const dot = document.querySelector<HTMLElement>(
      '[data-component="ticket-card"] [data-state-dot]',
    );
    expect(dot).not.toBeNull();
    expect(getComputedStyle(dot!).animationName).toBe("none");
  });

  // ------------------------------------------------------------------
  // 补充测试：覆盖 selected=true 边条、events 展示、未知 state 回退 + console.warn、
  // tool=opencode 分支、skill 缺失 fallback。
  // Traces To §BC state 9 态枚举外回退 pending + §VRC TicketCard tool chip /
  // state-dot / selected 变体 + §IC postcondition（selected=true → 3px state 色条）。
  // ------------------------------------------------------------------
  it("selected=true —— 渲染左侧 3px 色条（position:absolute, left:0, width:3）", () => {
    mockMatchMedia(false);
    const { container } = render(
      <TicketCard id="t-sel" state="completed" status="完成" skill="x" selected />,
    );
    const bar = container.querySelector<HTMLElement>(
      '[data-component="ticket-card"] > div[style*="position: absolute"]',
    );
    expect(bar).not.toBeNull();
    expect(bar!.style.width).toBe("3px");
    expect(bar!.style.left).toBe("0px");
  });

  it("events!=null —— 渲染 'N events' 文本（events 分支）", () => {
    mockMatchMedia(false);
    const { container } = render(
      <TicketCard id="t-ev" state="running" status="..." skill="x" events={42} />,
    );
    expect(container.textContent).toContain("42 events");
  });

  it("events=undefined —— 不渲染 events 节点", () => {
    mockMatchMedia(false);
    const { container } = render(
      <TicketCard id="t-nev" state="running" status="..." skill="x" />,
    );
    expect(container.textContent).not.toMatch(/events/);
  });

  it("未知 state 回退 pending 视觉 + console.warn", () => {
    mockMatchMedia(false);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      // 故意类型断言绕过枚举以测试运行时兜底
      <TicketCard id="t-bad" state={"garbage" as unknown as "pending"} status="..." />,
    );
    expect(warn).toHaveBeenCalled();
    expect(String(warn.mock.calls[0][0])).toMatch(/unknown state/);
    const dot = document.querySelector<HTMLElement>(
      '[data-component="ticket-card"] [data-state-dot]',
    );
    // 回退到 pending —— 不含 pulse
    expect(dot!.classList.contains("pulse")).toBe(false);
    warn.mockRestore();
  });

  it("tool='opencode' —— chip color=rgb(125,219,211) + label='opencode'", () => {
    mockMatchMedia(false);
    render(
      <TicketCard id="t-oc" state="running" status="..." skill="x" tool="opencode" />,
    );
    const chip = document.querySelector<HTMLElement>(
      '[data-component="ticket-card"] [data-tool="opencode"]',
    );
    expect(chip).not.toBeNull();
    expect(chip!).toHaveTextContent("opencode");
    expect(getComputedStyle(chip!).color).toBe("rgb(125, 219, 211)");
  });

  it("skill 缺失 —— 渲染 '(no skill)' 占位", () => {
    mockMatchMedia(false);
    const { container } = render(
      <TicketCard id="t-noskill" state="running" status="..." />,
    );
    expect(container.textContent).toContain("(no skill)");
  });
});
