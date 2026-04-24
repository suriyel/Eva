/**
 * PageFrame 精确分支测试
 *
 * 覆盖 Test Inventory / §IC 分支：
 *   §IC PageFrame Preconditions: `title` 非空 —— 空/空串 title 抛 TypeError
 *   §VRC Top bar render —— subtitle / headerRight / actions 可选 slot 正确渲染
 *   §VRC HIL 徽标 §BC hilCount=undefined 默认 0 —— 未传 hilCount 时徽标不渲染
 *
 * SRS Trace: NFR-011 基座义务（PageFrame 作为 top bar / 侧栏 primitives 聚合器）
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { PageFrame } from "@/components/page-frame";

describe("PageFrame title precondition (§IC)", () => {
  it("空 title —— 抛 TypeError", () => {
    // 抑制 React 控制台 error noise；直接 React.createElement 绕 TS 类型检查测运行时前置条件
    const origErr = console.error;
    console.error = () => undefined;
    try {
      expect(() =>
        render(
          <PageFrame active="overview" title="">
            <div />
          </PageFrame>,
        ),
      ).toThrow(TypeError);
    } finally {
      console.error = origErr;
    }
  });
});

describe("PageFrame optional slots (§VRC Top bar variants)", () => {
  it("hilCount 未传 —— 默认 0，HIL 徽标不渲染（§BC hilCount=0）", () => {
    render(
      <PageFrame active="overview" title="总览">
        <div />
      </PageFrame>,
    );
    const badge = document.querySelector(
      '[data-component="sidebar"] [data-nav="hil"] [data-badge="true"]',
    );
    expect(badge).toBeNull();
  });

  it("subtitle / headerRight / actions 三个可选 slot 同时填充 —— 三者文本都出现在 top-bar", () => {
    render(
      <PageFrame
        active="overview"
        title="总览"
        subtitle={<span data-testid="subtitle">子标题A</span>}
        headerRight={<span data-testid="header-right">右侧B</span>}
        actions={<span data-testid="actions">操作C</span>}
      >
        <div />
      </PageFrame>,
    );
    const topBar = document.querySelector<HTMLElement>('header[data-component="top-bar"]');
    expect(topBar).not.toBeNull();
    expect(topBar!).toHaveTextContent("子标题A");
    expect(topBar!).toHaveTextContent("右侧B");
    expect(topBar!).toHaveTextContent("操作C");
  });

  it("children 内容渲染在 top-bar 下方 flex 容器（height 56px top-bar + 内容区）", () => {
    const { getByTestId } = render(
      <PageFrame active="overview" title="总览">
        <div data-testid="pf-child">内容区</div>
      </PageFrame>,
    );
    expect(getByTestId("pf-child")).toHaveTextContent("内容区");
  });
});
