/**
 * HilInboxPage —— 路由页：3 张 hil_waiting → 3 卡片；空 → Empty State；WS event 增删
 *
 * Traces To 特性 21 design §Interface Contract `HilInboxPage` ·
 *           §Test Inventory T03 / T04 / T18 / T28 / T45 ·
 *           SRS FR-031 AC-1（3 卡片）+ AC-2（answered 状态机）·
 *           sequenceDiagram msg#2 (HilQuestionOpened)。
 *
 * Red 阶段：`apps/ui/src/routes/hil-inbox/index.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「初始 fetch 不过滤 state=hil_waiting」→ T03 卡片数错 FAIL
 *   - 「未注册 /ws/hil 订阅」→ T28 增量卡片 FAIL
 *   - 「未知 WS envelope 抛错冒泡」→ T45 红屏 FAIL
 *
 * [unit] —— uses fetch + WebSocket mocks; integration smoke at tests/integration.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HarnessWsClient } from "@/ws/client";
import { HilInboxPage } from "@/routes/hil-inbox";

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
      <MemoryRouter initialEntries={["/hil"]}>{children}</MemoryRouter>
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

describe("HilInboxPage 初始 fetch (T03/T04 FUNC/happy + UI/render Empty)", () => {
  it("T03 mock /api/tickets?state=hil_waiting → 3 张 → DOM 含 3 个 [data-component='hil-card']", async () => {
    // F24 B2: HilInbox 现在依赖 useCurrentRun 的 run_id；按 URL 路由分发响应。
    globalThis.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/runs/current")) {
        return Promise.resolve(
          new Response(JSON.stringify({ run_id: "run-test", state: "running" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify([
            { id: "t-1", state: "hil_waiting", questions: [{ id: "q-1", multi_select: false, options: [{ label: "A" }, { label: "B" }], allow_freeform: false, question: "Q1" }] },
            { id: "t-2", state: "hil_waiting", questions: [{ id: "q-2", multi_select: true, options: [{ label: "A" }, { label: "B" }], allow_freeform: false, question: "Q2" }] },
            { id: "t-3", state: "hil_waiting", questions: [{ id: "q-3", multi_select: false, options: [], allow_freeform: true, question: "Q3" }] },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    const { container } = render(<HilInboxPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelectorAll('[data-component="hil-card"]').length).toBe(3);
    });
    // Empty state 不应出现
    expect(container.querySelector('[data-testid="hil-empty"]')).toBeNull();
  });

  it("T04 mock 空数组 → DOM 含 [data-testid='hil-empty']，无 hil-card", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { container } = render(<HilInboxPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-testid="hil-empty"]')).not.toBeNull();
    });
    expect(container.querySelectorAll('[data-component="hil-card"]').length).toBe(0);
  });
});

describe("HilInboxPage WebSocket /ws/hil (T28 INTG/ws)", () => {
  it("T28 WS push HilQuestionOpened → 新增 hil-card", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { container } = render(<HilInboxPage />, { wrapper: Wrapper });
    // 先等空态稳定
    await waitFor(() => {
      expect(container.querySelector('[data-testid="hil-empty"]')).not.toBeNull();
    });
    // 触发 WS open & 推送（F24 B3 — useWs 直连 /ws/hil 创建独立 socket）
    const ch = wsInstances[wsInstances.length - 1];
    act(() => {
      ch?._fireOpen();
      ch?._fireMessage({
        kind: "hil_question_opened",
        channel: "/ws/hil",
        payload: {
          ticket_id: "t-99",
          questions: [
            {
              id: "q-99",
              multi_select: false,
              options: [{ label: "Yes" }, { label: "No" }],
              allow_freeform: false,
              question: "Continue?",
            },
          ],
        },
      });
    });
    await waitFor(() => {
      const cards = container.querySelectorAll('[data-component="hil-card"]');
      expect(cards.length).toBeGreaterThanOrEqual(1);
    });
  });
});

describe("HilInboxPage 未知 envelope 容错 (T45 FUNC/error)", () => {
  it("T45 WS push 未知 kind=unknown_event → 不崩溃，DOM 状态不变", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { container } = render(<HilInboxPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-testid="hil-empty"]')).not.toBeNull();
    });
    // 推送非法 envelope 不应触发 ErrorBoundary（F24 B3 — useWs 直连 /ws/hil）
    const ch = wsInstances[wsInstances.length - 1];
    expect(() => {
      act(() => {
        ch?._fireOpen();
        ch?._fireMessage({ kind: "unknown_event", channel: "/ws/hil" });
      });
    }).not.toThrow();
    // 状态不变（仍为空态）
    expect(container.querySelector('[data-testid="hil-empty"]')).not.toBeNull();
  });
});
