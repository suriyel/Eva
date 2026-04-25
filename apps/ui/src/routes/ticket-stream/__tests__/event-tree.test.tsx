/**
 * EventTree —— 虚拟滚动 stream-event 行视图分支覆盖
 *
 * Traces To 特性 21 design §Visual Rendering Contract Event row · §VRC inline search ·
 *           §Test Inventory T24 / T25 / T27 ·
 *           SRS FR-034 AC-1（事件流可视化）+ NFR-002 AC-1（10k 事件不卡）。
 *
 * [unit] —— happy-dom 下 useVirtualizer items 为空 → 走 fallback 渲染分支；
 *           本测试覆盖 KIND_COLOR fallback、searchHits 命中、summarizePayload 三种 payload。
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { EventTree, type StreamEventLike } from "@/routes/ticket-stream/components/event-tree";

describe("EventTree fallback 渲染（FR-034 / NFR-002）", () => {
  it("T24 events=[] → 不渲染任何行（fallbackRange 长度 0）", () => {
    const { container } = render(<EventTree events={[]} />);
    const total = container.querySelector("[data-component=event-tree]");
    expect(total).not.toBeNull();
    expect(total!.getAttribute("data-row-total")).toBe("0");
    expect(container.querySelectorAll("[data-row-index]").length).toBe(0);
  });

  it("T24 events 长度 3 → fallback 渲染 3 行（happy-dom virtualizer items=[]）", () => {
    const events: StreamEventLike[] = [
      { seq: 1, kind: "tool_use", payload: { name: "Read" } },
      { seq: 2, kind: "text", payload: "hello" },
      { seq: 3, kind: "unknown_kind", payload: null },
    ];
    const { container } = render(<EventTree events={events} />);
    const rows = container.querySelectorAll("[data-row-index]");
    expect(rows.length).toBe(3);
    // 颜色 fallback 分支：unknown_kind 走默认色
    expect(rows[2].getAttribute("data-kind")).toBe("unknown_kind");
  });

  it("T27 onSelect 在行点击时被调用且参数为对应事件", () => {
    const events: StreamEventLike[] = [{ seq: 9, kind: "text", payload: "hi" }];
    const onSelect = vi.fn();
    const { container } = render(<EventTree events={events} onSelect={onSelect} />);
    const row = container.querySelector("[data-row-index='0']") as HTMLElement;
    row.click();
    expect(onSelect).toHaveBeenCalledWith(events[0]);
  });

  it("行点击但未传 onSelect 不抛错（可选回调分支）", () => {
    const events: StreamEventLike[] = [{ seq: 1, kind: "text", payload: "x" }];
    const { container } = render(<EventTree events={events} />);
    const row = container.querySelector("[data-row-index='0']") as HTMLElement;
    expect(() => row.click()).not.toThrow();
  });

  it("T36 searchHits 命中索引 → 渲染 <mark data-search-hit>（高亮分支）", () => {
    const events: StreamEventLike[] = [
      { seq: 1, kind: "text", payload: "alpha" },
      { seq: 2, kind: "text", payload: "beta" },
    ];
    const hits = new Set<number>([1]);
    const { container } = render(<EventTree events={events} searchHits={hits} />);
    const marks = container.querySelectorAll("mark[data-search-hit]");
    expect(marks.length).toBe(1);
    expect(marks[0].textContent).toBe("beta");
  });

  it("summarizePayload —— string payload 走 slice(0,120) 路径", () => {
    const long = "x".repeat(200);
    const events: StreamEventLike[] = [{ seq: 1, kind: "text", payload: long }];
    render(<EventTree events={events} />);
    // 文本被截到 120 字符
    expect(screen.getByText("x".repeat(120))).toBeTruthy();
  });

  it("summarizePayload —— null payload → 空字符串（不抛错）", () => {
    const events: StreamEventLike[] = [{ seq: 1, kind: "text", payload: null }];
    const { container } = render(<EventTree events={events} />);
    expect(container.querySelectorAll("[data-row-index]").length).toBe(1);
  });

  it("summarizePayload —— 不可序列化 payload（含循环引用）走 catch 分支返回 ''", () => {
    const cyc: Record<string, unknown> = {};
    cyc.self = cyc;
    const events: StreamEventLike[] = [{ seq: 1, kind: "tool_result", payload: cyc }];
    const { container } = render(<EventTree events={events} />);
    expect(container.querySelectorAll("[data-row-index]").length).toBe(1);
  });

  it("onWheel 透传到容器（usePauseScrollOnInteraction 集成口）", () => {
    const events: StreamEventLike[] = [{ seq: 1, kind: "text", payload: "y" }];
    const onWheel = vi.fn();
    const { container } = render(<EventTree events={events} onWheel={onWheel} />);
    const root = container.querySelector("[data-component=event-tree]") as HTMLElement;
    // 派发 wheel 事件
    root.dispatchEvent(new WheelEvent("wheel", { deltaY: -50, bubbles: true }));
    expect(onWheel).toHaveBeenCalled();
  });

  it("KIND_COLOR 各 kind 都至少能渲染一行（不抛错）", () => {
    const kinds = ["tool_use", "tool_result", "text", "thinking", "error", "denied"];
    const events: StreamEventLike[] = kinds.map((k, i) => ({
      seq: i + 1,
      kind: k,
      payload: `p-${i}`,
    }));
    const { container } = render(<EventTree events={events} />);
    const rows = container.querySelectorAll("[data-row-index]");
    expect(rows.length).toBe(kinds.length);
  });
});
