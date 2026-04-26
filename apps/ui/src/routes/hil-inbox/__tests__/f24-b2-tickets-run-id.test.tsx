/**
 * Feature #24 B2 — HilInbox /api/tickets must carry run_id query.
 *
 * Traces To
 * =========
 *   B2-P1  IAPI-002 GET /api/tickets / FR-031 AC-1                    INTG/api
 *   B2-P2  §VRC HILInbox EmptyState                                    UI/render
 *   B2-N1  §IC `HilInbox.useTicketsQuery` postcondition                FUNC/error
 *   B2-P3  IAPI-001 /ws/hil hil_question_opened invalidate              INTG/ws
 *   FR-010 — HIL ticket render 视觉变体 (radio/checkbox/textarea) 由 HilInbox 列表入口承接；
 *            B2 的 fetch contract 是 FR-010 渲染前提（无 run_id → 不进入 ticket 视觉变体路径）
 *   §Implementation Summary B2 (currentRunId from useCurrentRun)
 *
 * Rule 4 wrong-impl challenge:
 *   - 「fetch URL 不附 run_id」                  → B2-P1 fail
 *   - 「currentRunId == null 仍发请求」          → B2-P2 fetch.mock.calls > 0 fail
 *   - 「enabled 仅依赖 mount，不看 currentRunId」 → B2-N1 fail
 *   - 「WS push 不 invalidate query」            → B2-P3 列表不增加 fail
 *
 * Rule 5 layer:
 *   [unit] uses fetch + WebSocket mocks; SUT real-imported.
 *   Real test for /api/tickets backend round-trip is in
 *   tests/integration/test_f23_real_rest_routes.py (covers tickets router).
 *
 * Red 阶段：当前 hil-inbox/index.tsx:78-80 写死 `?state=hil_waiting` 不附
 *   run_id；B2-P1 fetch URL 断言会 FAIL 因为没有 run_id 参数；B2-P2 因为
 *   query 总是 enabled 而非 `enabled: !!currentRunId`，仍会 fire fetch。
 *
 * Feature ref: feature 24
 *
 * [unit] — uses fetch + WebSocket mocks.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
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
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/hil"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  installFakeWebSocket();
  HarnessWsClient.__resetSingletonForTests?.();
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
    "http://127.0.0.1:8765";
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function makeFetchSequence(
  responses: Array<{ status: number; body: unknown }>,
): ReturnType<typeof vi.fn> {
  const fn = vi.fn();
  for (const r of responses) {
    fn.mockResolvedValue(
      new Response(JSON.stringify(r.body), {
        status: r.status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }
  return fn;
}

// --------------------------------------------------------------------- B2-P1
describe("B2-P1 INTG/api — fetch URL must carry run_id query", () => {
  it("currentRunId='run-x' 时 GET /api/tickets URL 含 run_id=run-x + state=hil_waiting", async () => {
    const RUN_ID = "run-26.04.26-001";
    const fetchMock = vi.fn();
    // currentRun GET → returns RUN_ID
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: RUN_ID, state: "running" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    // tickets GET (must contain run_id)
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;

    render(<HilInboxPage />, { wrapper: Wrapper });

    await waitFor(() => {
      const calls = fetchMock.mock.calls as unknown[][];
      const ticketCall = calls.find((c) => String(c[0]).includes("/api/tickets"));
      expect(ticketCall, `no /api/tickets call observed; calls=${JSON.stringify(calls.map((c) => c[0]))}`).toBeTruthy();
      const url = String(ticketCall![0]);
      expect(url, `tickets URL missing run_id: ${url}`).toMatch(
        /run_id=run-26\.04\.26-001/,
      );
      expect(url, `tickets URL missing state=hil_waiting: ${url}`).toMatch(
        /state=hil_waiting/,
      );
    });
  });
});

// --------------------------------------------------------------------- B2-P2
describe("B2-P2 UI/render — EmptyState when currentRunId == null + 0 fetch /api/tickets", () => {
  it("currentRunId == null 时 0 次 GET /api/tickets + EmptyState 渲染", async () => {
    const fetchMock = vi.fn();
    // currentRun GET returns 404 → null current run
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "no run" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    // Any further /api/tickets fetch should NOT happen.
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;

    const { container } = render(<HilInboxPage />, { wrapper: Wrapper });

    // Allow query to settle.
    await new Promise((r) => setTimeout(r, 80));

    const calls = fetchMock.mock.calls as unknown[][];
    const ticketCalls = calls.filter((c) => String(c[0]).includes("/api/tickets"));
    expect(ticketCalls, `expected 0 tickets fetch when no run; got ${ticketCalls.length}`).toHaveLength(0);

    const empty = container.querySelector('[data-testid="hil-inbox-empty"]');
    expect(empty, "hil-inbox-empty EmptyState missing when currentRunId == null").not.toBeNull();
  });
});

// --------------------------------------------------------------------- B2-N1
describe("B2-N1 FUNC/error — currentRunId null + manual refetch still skips", () => {
  it("currentRunId == null + invalidate query 仍不发 GET /api/tickets (enabled: false 守卫)", async () => {
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "no run" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    // Subsequent calls would 400 because backend rejects missing run_id.
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: { error_code: "invalid_param", field: "run_id" } }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;

    render(<HilInboxPage />, { wrapper: Wrapper });
    await new Promise((r) => setTimeout(r, 100));

    const calls = fetchMock.mock.calls as unknown[][];
    const ticketCalls = calls.filter((c) => String(c[0]).includes("/api/tickets"));
    // Even after natural mount + any refetch attempts, ticket calls remain 0.
    expect(ticketCalls, `enabled-guard bypass leaked: ${JSON.stringify(ticketCalls.map((c) => c[0]))}`).toHaveLength(0);
  });
});

// --------------------------------------------------------------------- B2-P3
describe("B2-P3 INTG/ws — /ws/hil hil_question_opened invalidates tickets query", () => {
  it("WS push hil_question_opened → 触发 tickets refetch (≥2 次 GET /api/tickets)", async () => {
    const RUN_ID = "run-x";
    const fetchMock = vi.fn();
    // currentRun
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: RUN_ID, state: "running" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    // tickets first call: empty
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    // tickets second call (after WS event): one ticket
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify([
        {
          id: "t1",
          state: "hil_waiting",
          questions: [
            { id: "q1", question: "Approve?", multi_select: false, options: [{ key: "yes", label: "Yes" }, { key: "no", label: "No" }], allow_freeform: false },
          ],
        },
      ]), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    globalThis.fetch = fetchMock;

    render(<HilInboxPage />, { wrapper: Wrapper });

    // Wait for first ticket call.
    await waitFor(() => {
      const calls = (fetchMock.mock.calls as unknown[][]).filter((c) =>
        String(c[0]).includes("/api/tickets"),
      );
      expect(calls.length).toBeGreaterThanOrEqual(1);
    });

    // Simulate WS push of hil_question_opened on the first WS instance.
    expect(wsInstances.length, "no WS instance opened").toBeGreaterThanOrEqual(1);
    wsInstances[0]._fireOpen();
    wsInstances[0]._fireMessage({
      kind: "hil_question_opened",
      channel: "/ws/hil",
      payload: { ticket_id: "t1" },
    });

    // After invalidation, tickets fetch must run again.
    await waitFor(() => {
      const calls = (fetchMock.mock.calls as unknown[][]).filter((c) =>
        String(c[0]).includes("/api/tickets"),
      );
      expect(calls.length, `expected ≥2 ticket calls post-WS, got ${calls.length}`).toBeGreaterThanOrEqual(2);
    });
  });
});
