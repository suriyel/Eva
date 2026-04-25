/**
 * useInlineSearch —— Ctrl/Cmd+F 命中 hook
 *
 * Traces To 特性 21 design §Interface Contract `useInlineSearch` ·
 *           §Test Inventory T36 ·
 *           §VRC inline search ·
 *           SRS FR-034 AC-2（内联搜索高亮）。
 *
 * [unit] —— renderHook + window.dispatchEvent KeyboardEvent。
 */
import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useInlineSearch } from "@/routes/ticket-stream/use-inline-search";
import type { StreamEventLike } from "@/routes/ticket-stream/components/event-tree";

const events: StreamEventLike[] = [
  { seq: 1, kind: "tool_use", payload: { name: "Read", input: { path: "a.ts" } } },
  { seq: 2, kind: "text", payload: "hello world" },
  { seq: 3, kind: "tool_use", payload: { name: "Bash", input: { cmd: "ls" } } },
  { seq: 4, kind: "text", payload: null },
];

describe("useInlineSearch —— FR-034 inline search hits", () => {
  it("T36 初始 query='' → hits=[]（空查询不命中任何行）", () => {
    const { result } = renderHook(() => useInlineSearch(events));
    expect(result.current.query).toBe("");
    expect(result.current.hits).toEqual([]);
  });

  it("T36 setQuery('hello') → hits=[1]（仅命中 seq=2 索引 1 行）", () => {
    const { result } = renderHook(() => useInlineSearch(events));
    act(() => {
      result.current.setQuery("hello");
    });
    expect(result.current.hits).toEqual([1]);
  });

  it("T36 大小写不敏感 setQuery('READ') → hits=[0]", () => {
    const { result } = renderHook(() => useInlineSearch(events));
    act(() => {
      result.current.setQuery("READ");
    });
    expect(result.current.hits).toEqual([0]);
  });

  it("T36 多命中 setQuery('tool') 不应命中（'tool' 是 kind 字段非 payload）", () => {
    // payload only is searched per design contract
    const { result } = renderHook(() => useInlineSearch(events));
    act(() => {
      result.current.setQuery("tool");
    });
    // None of the payload JSONs contain the word "tool"
    expect(result.current.hits).toEqual([]);
  });

  it("T36 payload 缺失（null）路径走 ?? '' 分支不抛错且不命中 'null' 字面量", () => {
    const { result } = renderHook(() => useInlineSearch(events));
    act(() => {
      result.current.setQuery("null");
    });
    // payload null → ev.payload ?? "" === "" → 不含 'null' 字符串
    expect(result.current.hits).toEqual([]);
    // 但 query 路径仍可命中其他事件（验证 forEach 在 null payload 时未抛）
    act(() => {
      result.current.setQuery("hello");
    });
    expect(result.current.hits).toEqual([1]);
  });

  it("T36 Ctrl+F preventDefault + focus 输入框（registers + cleanup keydown listener）", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useInlineSearch(events));
    expect(addSpy).toHaveBeenCalledWith("keydown", expect.any(Function));

    // 触发 Ctrl+F：handler 应当 preventDefault（搜索输入框未挂载 → focus 跳过 chain ?.）
    const ctrlF = new KeyboardEvent("keydown", { key: "f", ctrlKey: true });
    const preventSpy = vi.spyOn(ctrlF, "preventDefault");
    window.dispatchEvent(ctrlF);
    expect(preventSpy).toHaveBeenCalled();

    // 大写 F + meta 键路径
    const metaF = new KeyboardEvent("keydown", { key: "F", metaKey: true });
    const metaPrevent = vi.spyOn(metaF, "preventDefault");
    window.dispatchEvent(metaF);
    expect(metaPrevent).toHaveBeenCalled();

    // 非 F 键 → 不触发 preventDefault
    const ctrlA = new KeyboardEvent("keydown", { key: "a", ctrlKey: true });
    const ctrlAPrevent = vi.spyOn(ctrlA, "preventDefault");
    window.dispatchEvent(ctrlA);
    expect(ctrlAPrevent).not.toHaveBeenCalled();

    // 无修饰键 + f → 不触发
    const plainF = new KeyboardEvent("keydown", { key: "f" });
    const plainPrevent = vi.spyOn(plainF, "preventDefault");
    window.dispatchEvent(plainF);
    expect(plainPrevent).not.toHaveBeenCalled();

    unmount();
    expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
    addSpy.mockRestore();
    removeSpy.mockRestore();
  });
});
