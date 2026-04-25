/**
 * useTicketStreamFilters —— URL ?state=&tool=&run_id=&parent= 同步 hook
 *
 * Traces To 特性 21 design §Interface Contract `useTicketStreamFilters` ·
 *           §Test Inventory T37 / T38 ·
 *           SRS FR-034 AC-1（筛选 tool=claude）+ Boundary Conditions URL 非法值。
 *
 * Red 阶段：`use-filters.ts` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「setFilter 不更新 URL」→ T37 URL 同步 FAIL
 *   - 「非法 enum 值不被清理」→ T38 URL 残留 FAIL
 *
 * [unit] —— uses MemoryRouter; no real browser navigation.
 */
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { useTicketStreamFilters } from "@/routes/ticket-stream/use-filters";

interface HarnessProps {
  initial: string;
  children: React.ReactNode;
}

function Harness({ initial, children }: HarnessProps): React.ReactElement {
  return (
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path="/ticket-stream" element={<>{children}</>} />
      </Routes>
    </MemoryRouter>
  );
}

function useFiltersAndLocation(): {
  filters: ReturnType<typeof useTicketStreamFilters>["filters"];
  setFilter: ReturnType<typeof useTicketStreamFilters>["setFilter"];
  search: string;
} {
  const { filters, setFilter } = useTicketStreamFilters();
  const loc = useLocation();
  return { filters, setFilter, search: loc.search };
}

describe("useTicketStreamFilters URL ↔ state 同步", () => {
  it("T37 初始 URL ?state=running&tool=claude → filters 同步", () => {
    const { result } = renderHook(() => useFiltersAndLocation(), {
      wrapper: ({ children }) => (
        <Harness initial="/ticket-stream?state=running&tool=claude">{children}</Harness>
      ),
    });
    expect(result.current.filters.state).toBe("running");
    expect(result.current.filters.tool).toBe("claude");
  });

  it("T37b setFilter('tool','opencode') → URL 同步为 ?tool=opencode 且保留其他 param", () => {
    const { result } = renderHook(() => useFiltersAndLocation(), {
      wrapper: ({ children }) => (
        <Harness initial="/ticket-stream?state=running&tool=claude">{children}</Harness>
      ),
    });
    act(() => {
      result.current.setFilter("tool", "opencode");
    });
    expect(result.current.search).toContain("tool=opencode");
    expect(result.current.search).toContain("state=running");
    expect(result.current.search).not.toContain("tool=claude");
    expect(result.current.filters.tool).toBe("opencode");
  });

  it("T38 BNDRY/edge —— URL ?tool=foo（不在 enum）→ filter 忽略且 URL 清理", () => {
    const { result } = renderHook(() => useFiltersAndLocation(), {
      wrapper: ({ children }) => <Harness initial="/ticket-stream?tool=foo">{children}</Harness>,
    });
    // filter 不接受非法值
    expect(result.current.filters.tool).toBeUndefined();
    // URL 同步清理：search 中不再含 tool=foo
    expect(result.current.search).not.toContain("tool=foo");
  });

  it("setFilter(key, undefined) 移除该 param（不污染 URL 空值）", () => {
    const { result } = renderHook(() => useFiltersAndLocation(), {
      wrapper: ({ children }) => (
        <Harness initial="/ticket-stream?tool=claude&state=running">{children}</Harness>
      ),
    });
    act(() => {
      result.current.setFilter("tool", undefined);
    });
    expect(result.current.search).not.toContain("tool=");
    expect(result.current.search).toContain("state=running");
  });
});
