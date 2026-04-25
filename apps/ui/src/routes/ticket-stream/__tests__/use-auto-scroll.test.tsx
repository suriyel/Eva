/**
 * usePauseScrollOnInteraction —— 用户向上滚 → 暂停 auto-scroll-to-bottom
 *
 * Traces To 特性 21 design §Interface Contract `usePauseScrollOnInteraction` ·
 *           §Test Inventory T35 ·
 *           §VRC auto-scroll-indicator ·
 *           SRS FR-034 AC-1（事件流可视化交互）。
 *
 * [unit] —— pure hook; no DOM event source needed.
 */
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePauseScrollOnInteraction } from "@/routes/ticket-stream/use-auto-scroll";

describe("usePauseScrollOnInteraction —— FR-034 auto-scroll pause", () => {
  it("T35 初始 paused=false", () => {
    const { result } = renderHook(() => usePauseScrollOnInteraction());
    expect(result.current.paused).toBe(false);
  });

  it("T35 onWheel(deltaY<0) → paused=true（向上滚 → 暂停）", () => {
    const { result } = renderHook(() => usePauseScrollOnInteraction());
    act(() => {
      result.current.onWheel(-30);
    });
    expect(result.current.paused).toBe(true);
  });

  it("T35 onWheel(deltaY>=0) 不会暂停（向下滚保留 auto-scroll）", () => {
    const { result } = renderHook(() => usePauseScrollOnInteraction());
    act(() => {
      result.current.onWheel(40);
    });
    expect(result.current.paused).toBe(false);
    act(() => {
      result.current.onWheel(0);
    });
    expect(result.current.paused).toBe(false);
  });

  it("T35 resume() 把 paused 重置回 false", () => {
    const { result } = renderHook(() => usePauseScrollOnInteraction());
    act(() => {
      result.current.onWheel(-10);
    });
    expect(result.current.paused).toBe(true);
    act(() => {
      result.current.resume();
    });
    expect(result.current.paused).toBe(false);
  });
});
