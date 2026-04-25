/**
 * HILCard —— 三变体（radio/checkbox/textarea）正向渲染 + 标注 chip + XSS 字面量
 *
 * Traces To 特性 21 design §Visual Rendering Contract HILCard rows ·
 *           §Test Inventory T12 / T13 / T14 / T15 / T16 / T40 / T44 ·
 *           SRS FR-010 + FR-031 SEC + NFR-011（控件标注 "单选/多选/自由文本"）。
 *
 * Red 阶段：`components/hil-card.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 6/7 UI：每变体的正向 DOM 断言 + 标注文案 + XSS 不被解析为 HTML 节点。
 *
 * [unit] —— uses happy-dom; integration covered by tests/integration/test_f21_real_websocket.py.
 */
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import * as React from "react";
import { HILCard } from "@/routes/hil-inbox/components/hil-card";

describe("HILCard radio (T12)", () => {
  it("T12 variant=radio + 2 options → 渲染 [role='radio'] × 2，无 checkbox/textarea", () => {
    const { container } = render(
      <HILCard
        ticketId="t-1"
        questionId="q-1"
        variant="radio"
        question="选一个"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Requirements"
      />,
    );
    expect(container.querySelectorAll('[role="radio"]').length).toBe(2);
    expect(container.querySelectorAll('[role="checkbox"]').length).toBe(0);
    expect(container.querySelectorAll("textarea").length).toBe(0);
  });

  it("T15a 控件标注 chip 文案 = '单选'（NFR-011）", () => {
    const { container } = render(
      <HILCard
        ticketId="t-1"
        questionId="q-1"
        variant="radio"
        question="选一个"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Requirements"
      />,
    );
    const chip = container.querySelector('[data-testid="control-label"]');
    expect(chip?.textContent).toBe("单选");
  });
});

describe("HILCard checkbox (T13)", () => {
  it("T13 variant=checkbox → 渲染 [role='checkbox']", () => {
    const { container } = render(
      <HILCard
        ticketId="t-2"
        questionId="q-2"
        variant="checkbox"
        question="多选题"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Design"
      />,
    );
    expect(container.querySelectorAll('[role="checkbox"]').length).toBeGreaterThanOrEqual(1);
    expect(container.querySelectorAll('[role="radio"]').length).toBe(0);
  });

  it("T15b 控件标注 chip 文案 = '多选'（NFR-011）", () => {
    const { container } = render(
      <HILCard
        ticketId="t-2"
        questionId="q-2"
        variant="checkbox"
        question="多选题"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Design"
      />,
    );
    expect(container.querySelector('[data-testid="control-label"]')?.textContent).toBe("多选");
  });
});

describe("HILCard textarea (T14)", () => {
  it("T14 variant=textarea → 渲染 <textarea>", () => {
    const { container } = render(
      <HILCard
        ticketId="t-3"
        questionId="q-3"
        variant="textarea"
        question="自由文本"
        options={[]}
        phase="Design"
      />,
    );
    expect(container.querySelectorAll("textarea").length).toBe(1);
    expect(container.querySelectorAll('[role="radio"]').length).toBe(0);
    expect(container.querySelectorAll('[role="checkbox"]').length).toBe(0);
  });

  it("T15c 控件标注 chip 文案 = '自由文本'（NFR-011）", () => {
    const { container } = render(
      <HILCard
        ticketId="t-3"
        questionId="q-3"
        variant="textarea"
        question="自由文本"
        options={[]}
        phase="Design"
      />,
    );
    expect(container.querySelector('[data-testid="control-label"]')?.textContent).toBe("自由文本");
  });
});

describe("HILCard phase 色带 header (T16/T44)", () => {
  it("T16/T44 header 应用 linear-gradient 含 phase 色 token (var(--phase-*)) ", () => {
    const { container } = render(
      <HILCard
        ticketId="t-4"
        questionId="q-4"
        variant="radio"
        question="phase 色带"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Design"
        phaseColor="var(--phase-design)"
      />,
    );
    const header = container.querySelector('[data-component="hil-card"] header');
    expect(header).not.toBeNull();
    // happy-dom GRADIENT_REGEXP `^...gradient\(([^)]+)\)$` 拒绝 `var(--…)`
    // 因 var() 含 `)` —— style.background / style.backgroundImage 因此为空。
    // 同等等价的可观察事实：React 写入 `style` 属性的原始文本（attribute 字符串）
    // 一定包含 linear-gradient + var(--phase-design)（无验证管线）。
    // Drift 决议：保留视觉契约 —— 经 attribute 字符串验证（与 prototype HILInbox.jsx
    // L31-34 文本等价），happy-dom CSSOM 限制下唯一可证伪渠道。
    const styleAttr = (header as HTMLElement).getAttribute("style") ?? "";
    const bg =
      (header as HTMLElement).style.background ||
      (header as HTMLElement).style.backgroundImage ||
      styleAttr;
    expect(bg).toContain("linear-gradient");
    expect(bg).toContain("var(--phase-design)");
  });
});

describe("HILCard freeform XSS literal (T17/T40 SEC/xss)", () => {
  it("T40 textarea 用户输入 `<img src=x onerror=alert(1)>` —— DOM 中无新增 <img> 元素被解析", () => {
    const xss = "<img src=x onerror=alert(1)>";
    const { container } = render(
      <HILCard
        ticketId="t-5"
        questionId="q-5"
        variant="textarea"
        question="自由文本"
        options={[]}
        phase="Design"
        defaultFreeformText={xss}
      />,
    );
    // 字面量保留：textarea.value === 原文（不被 escape，亦不被解析为 HTML）
    const ta = container.querySelector("textarea") as HTMLTextAreaElement | null;
    expect(ta).not.toBeNull();
    expect(ta!.value).toBe(xss);
    // 关键：DOM tree 中**不**应出现新 <img> 元素被解析（验证未走 dangerouslySetInnerHTML）
    expect(container.querySelectorAll("img").length).toBe(0);
  });
});

describe("HILCard answered visual (T18 prepareView)", () => {
  it("T18 answered=true → 卡片 opacity=0.5（已答状态视觉）", () => {
    const { container } = render(
      <HILCard
        ticketId="t-6"
        questionId="q-6"
        variant="radio"
        question="answered"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Design"
        answered={true}
      />,
    );
    const card = container.querySelector('[data-component="hil-card"]') as HTMLElement | null;
    expect(card).not.toBeNull();
    // 直接读取内联 style.opacity，规避 happy-dom 不解析 var(--…) 的影响
    expect(card!.style.opacity).toBe("0.5");
  });
});

describe("HILCard toggle + submit 回调（FR-010 / FR-031）", () => {
  it("T-radio-toggle radio 点击 A 后再点 B → onSubmit 收到 ['B']（互斥）", () => {
    const onSubmit = vi.fn();
    const { container } = render(
      <HILCard
        ticketId="t-r"
        questionId="q-r"
        variant="radio"
        question="单选"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Design"
        onSubmit={onSubmit}
      />,
    );
    const rows = container.querySelectorAll('[role="radio"]');
    fireEvent.click(rows[0] as HTMLElement);
    fireEvent.click(rows[1] as HTMLElement);
    const btn = container.querySelector('[data-testid="btn-submit-hil"]') as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onSubmit).toHaveBeenCalledWith(["B"], null);
  });

  it("T-checkbox-toggle checkbox 点 A、B、A → onSubmit 收到 ['B']（A toggle off）", () => {
    const onSubmit = vi.fn();
    const { container } = render(
      <HILCard
        ticketId="t-c"
        questionId="q-c"
        variant="checkbox"
        question="多选"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Design"
        onSubmit={onSubmit}
      />,
    );
    const rows = container.querySelectorAll('[role="checkbox"]');
    fireEvent.click(rows[0] as HTMLElement);
    fireEvent.click(rows[1] as HTMLElement);
    fireEvent.click(rows[0] as HTMLElement);
    const btn = container.querySelector('[data-testid="btn-submit-hil"]') as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onSubmit).toHaveBeenCalledWith(["B"], null);
  });

  it("T-textarea-submit textarea onChange 更新 + submit 携带 freeformText", () => {
    const onSubmit = vi.fn();
    const { container } = render(
      <HILCard
        ticketId="t-t"
        questionId="q-t"
        variant="textarea"
        question="自由"
        options={[]}
        phase="Design"
        onSubmit={onSubmit}
      />,
    );
    const ta = container.querySelector("textarea") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "我的回答" } });
    const btn = container.querySelector('[data-testid="btn-submit-hil"]') as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onSubmit).toHaveBeenCalledWith([], "我的回答");
  });

  it("T-submit-no-callback onSubmit 缺省时点击不抛错（可选回调分支）", () => {
    const { container } = render(
      <HILCard
        ticketId="t-x"
        questionId="q-x"
        variant="radio"
        question="无回调"
        options={[{ label: "A" }]}
        phase="Design"
      />,
    );
    const btn = container.querySelector('[data-testid="btn-submit-hil"]') as HTMLButtonElement;
    expect(() => fireEvent.click(btn)).not.toThrow();
  });

  it("T-submitting 提交中按钮文案=提交中… 且 disabled", () => {
    const { container } = render(
      <HILCard
        ticketId="t-s"
        questionId="q-s"
        variant="radio"
        question="提交中"
        options={[{ label: "A" }]}
        phase="Design"
        submitting={true}
      />,
    );
    const btn = container.querySelector('[data-testid="btn-submit-hil"]') as HTMLButtonElement;
    expect(btn.textContent).toBe("提交中…");
    expect(btn.disabled).toBe(true);
  });

  it("T-radio-with-freeform 控件 chip = '单选' 且同时渲染 textarea", () => {
    const { container } = render(
      <HILCard
        ticketId="t-rf"
        questionId="q-rf"
        variant="radio_with_freeform"
        question="带备注的单选"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Design"
      />,
    );
    expect(
      container.querySelector('[data-testid="control-label"]')?.textContent,
    ).toBe("单选");
    expect(container.querySelectorAll("textarea").length).toBe(1);
    // data-control 属性归一化为 'radio'
    expect(
      container
        .querySelector('[data-component="hil-card"]')
        ?.getAttribute("data-control"),
    ).toBe("radio");
  });

  it("T-checkbox-with-freeform 控件 chip = '多选' 且同时渲染 textarea + data-control=checkbox", () => {
    const { container } = render(
      <HILCard
        ticketId="t-cf"
        questionId="q-cf"
        variant="checkbox_with_freeform"
        question="带备注的多选"
        options={[{ label: "A" }, { label: "B" }]}
        phase="Design"
      />,
    );
    expect(
      container.querySelector('[data-testid="control-label"]')?.textContent,
    ).toBe("多选");
    expect(container.querySelectorAll("textarea").length).toBe(1);
    expect(
      container
        .querySelector('[data-component="hil-card"]')
        ?.getAttribute("data-control"),
    ).toBe("checkbox");
  });
});
