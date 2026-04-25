/**
 * RunOverviewPage —— 路由首屏：phase stepper + 6 元素 metrics + Empty State + pause/cancel
 *
 * Traces To 特性 21 design §Interface Contract `RunOverviewPage` / `pauseRun` / `cancelRun` ·
 *           §Test Inventory T01 / T02 / T29 / T31 / T32 / T33 / T34 ·
 *           SRS FR-030 AC-1（6 元素 + cost 总和）+ AC-2（work N/M）·
 *           §Visual Rendering Contract phase-stepper / run-cost / run-overview-empty。
 *
 * Red 阶段：`apps/ui/src/routes/run-overview/index.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「Empty 态忘渲染 [data-testid='run-overview-empty']」→ T34 FAIL
 *   - 「pause 调用错路径 / 静默失败」→ T31/T32 FAIL
 *   - 「cancel 不区分 404」→ T33 FAIL
 *
 * [unit] —— uses fetch + WebSocket mocks; integration via test_f21_real_websocket.py.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HarnessWsClient } from "@/ws/client";
import { RunOverviewPage } from "@/routes/run-overview";

const originalFetch = globalThis.fetch;

type MockWs = {
  sent: string[];
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  _fireOpen: () => void;
  _fireMessage: (payload: unknown) => void;
  send: (d: string) => void;
  close: () => void;
};
let wsInstances: MockWs[] = [];

function installFakeWebSocket(): void {
  wsInstances = [];
  globalThis.WebSocket = function (this: MockWs, _url: string) {
    this.sent = [];
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.send = (d: string) => {
      this.sent.push(d);
    };
    this.close = () => undefined;
    this._fireOpen = () => {
      this.onopen?.(new Event("open"));
    };
    this._fireMessage = (p: unknown) => {
      this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(p) }));
    };
    wsInstances.push(this);
  } as unknown as typeof WebSocket;
}

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  installFakeWebSocket();
  HarnessWsClient.__resetSingletonForTests();
  HarnessWsClient.singleton().connect("ws://127.0.0.1:8765");
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
    "http://127.0.0.1:8765";
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
  HarnessWsClient.__resetSingletonForTests();
});

const RUNNING_RUN = {
  run_id: "r-42",
  state: "running",
  current_phase: "design",
  cost_usd: 0,
  num_turns: 0,
  head_latest: "abc1234",
  started_at: "2026-04-25T08:00:00Z",
  ended_at: null,
  current_skill: "feature-design",
  current_feature: { id: 21, title: "F21 RunViews" },
  subprogress: null,
};

describe("RunOverviewPage 渲染 6 元素 (T01 FUNC/happy)", () => {
  it("T01 phase-stepper + 5 metric data-row + cost 总和 = Σ ticket.cost_usd", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(RUNNING_RUN), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const { container } = render(<RunOverviewPage />, { wrapper: Wrapper });
    // 等 fetch 落定
    await waitFor(() => {
      expect(container.querySelector('[data-component="phase-stepper"]')).not.toBeNull();
    });
    // 推 3 条 cost_usd=0.05
    act(() => {
      wsInstances[0]?._fireOpen();
      for (const ticketId of ["t-1", "t-2", "t-3"]) {
        wsInstances[0]?._fireMessage({
          kind: "ticket_state_changed",
          channel: "/ws/run/r-42",
          payload: { ticket_id: ticketId, cost_usd: 0.05, num_turns: 1 },
        });
      }
    });
    // cost = 0.15（容忍格式 `$0.15` 或 `0.15`）
    await waitFor(() => {
      const txt = container.querySelector('[data-testid="run-cost"]')?.textContent ?? "";
      expect(txt).toMatch(/0\.15/);
    });
    // phase stepper 子元素 ≥ 6（6 个 data-phase-index）
    const phaseSteps = container.querySelectorAll(
      '[data-component="phase-stepper"] [data-phase-index]',
    );
    expect(phaseSteps.length).toBeGreaterThanOrEqual(6);
  });

  it("T02 work 阶段 subprogress n=3,m=8 → DOM 含 'work 3/8' 或 '3/8' 字段", async () => {
    const wrk = { ...RUNNING_RUN, current_phase: "work", subprogress: { n: 3, m: 8 } };
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(wrk), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { container } = render(<RunOverviewPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.textContent ?? "").toMatch(/3\s*\/\s*8/);
    });
  });
});

describe("RunOverviewPage Empty State (T34 UI/render)", () => {
  it("T34 /api/runs/current 返回 null → DOM 含 [data-testid='run-overview-empty']", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("null", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { container } = render(<RunOverviewPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-testid="run-overview-empty"]')).not.toBeNull();
    });
    expect(container.querySelector('[data-component="phase-stepper"]')).toBeNull();
  });
});

describe("RunOverviewPage pause/cancel (T31/T32/T33 FUNC/happy + error)", () => {
  it("T31 click [data-testid='btn-pause'] → POST /api/runs/r-42/pause 发出", async () => {
    const fetchMock = vi
      .fn()
      // initial GET
      .mockResolvedValueOnce(
        new Response(JSON.stringify(RUNNING_RUN), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      // pause POST
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...RUNNING_RUN, state: "paused" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    globalThis.fetch = fetchMock;
    const { container } = render(<RunOverviewPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-testid="btn-pause"]')).not.toBeNull();
    });
    fireEvent.click(container.querySelector('[data-testid="btn-pause"]') as Element);
    await waitFor(() => {
      const calls = (fetchMock.mock.calls as unknown[][]).map((c) => String(c[0]));
      expect(calls.some((u) => u.includes("/api/runs/r-42/pause"))).toBe(true);
    });
    // method=POST
    const pauseCall = (fetchMock.mock.calls as unknown[][]).find((c) =>
      String(c[0]).includes("/pause"),
    );
    expect((pauseCall?.[1] as RequestInit | undefined)?.method).toBe("POST");
  });

  it("T32 pause 返回 409 → 抛 RunControlError code=STATE_CONFLICT", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(RUNNING_RUN), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "state not allowed" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      );
    globalThis.fetch = fetchMock;
    const { container } = render(<RunOverviewPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-testid="btn-pause"]')).not.toBeNull();
    });
    // 由于异步错误，断言：点击后短时间内出现错误状态指示元素 [data-testid='run-control-error']
    fireEvent.click(container.querySelector('[data-testid="btn-pause"]') as Element);
    await waitFor(() => {
      expect(container.querySelector('[data-testid="run-control-error"]')?.textContent).toContain(
        "STATE_CONFLICT",
      );
    });
  });

  it("T33 cancel 返回 404 → 错误指示含 RUN_NOT_FOUND", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(RUNNING_RUN), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "run not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      );
    globalThis.fetch = fetchMock;
    const { container } = render(<RunOverviewPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-testid="btn-cancel"]')).not.toBeNull();
    });
    fireEvent.click(container.querySelector('[data-testid="btn-cancel"]') as Element);
    await waitFor(() => {
      expect(container.querySelector('[data-testid="run-control-error"]')?.textContent).toContain(
        "RUN_NOT_FOUND",
      );
    });
  });
});
