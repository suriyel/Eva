/**
 * Feature #24 B2 — TicketStream default filters must inject currentRunId.
 *
 * Traces To
 * =========
 *   B2-N2  IAPI-002 / FR-034 / §IC `TicketStreamPage.buildTicketsUrl` postcondition
 *          (FUNC/error — default filters {state: undefined, run_id: undefined}
 *           must NOT fire GET /api/tickets that lacks run_id)         INTG/api
 *
 * Rule 4 wrong-impl challenge:
 *   - 「filters.run_id 默认 undefined → buildTicketsUrl 不附 run_id → fetch 命中
 *      backend 400」                                                      → fail
 *   - 「default filters 由 useTicketStreamFilters 自动注入 currentRunId」 → pass
 *
 * Rule 5 layer:
 *   [unit] uses fetch mocks; SUT TicketStreamPage real-imported.
 *
 * Red 阶段：当前 ticket-stream/index.tsx:60 默认 filters 无 run_id 注入 →
 *   buildTicketsUrl 返回不含 run_id 的 URL → fetch 命中 → backend 400 →
 *   本测试断言"无 run_id 时 0 次 fetch /api/tickets"会 FAIL.
 *
 * Feature ref: feature 24
 *
 * [unit] — uses fetch + WebSocket mocks; jsdom.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HarnessWsClient } from "@/ws/client";
import { TicketStreamPage } from "@/routes/ticket-stream";

const originalFetch = globalThis.fetch;

type MockWs = {
  sent: string[];
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  send: (d: string) => void;
  close: () => void;
};

beforeEach(() => {
  globalThis.WebSocket = function (this: MockWs, _url: string) {
    this.sent = [];
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.send = (d: string) => {
      this.sent.push(d);
    };
    this.close = () => undefined;
  } as unknown as typeof WebSocket;
  HarnessWsClient.__resetSingletonForTests?.();
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
    "http://127.0.0.1:8765";
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/ticket-stream"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

// --------------------------------------------------------------------- B2-N2
describe("B2-N2 INTG/api — TicketStream default filters skip fetch when no currentRun", () => {
  it("currentRunId == null + default filters → 0 次 GET /api/tickets (无 run_id 漏发 400)", async () => {
    const fetchMock = vi.fn();
    // currentRun returns 404 → no run.
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "no run" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    // Any subsequent /api/tickets call must not happen — but if it does,
    // backend 400 is what production returns today.
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: { error_code: "invalid_param", field: "run_id" } }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;

    render(<TicketStreamPage />, { wrapper: Wrapper });

    await new Promise((r) => setTimeout(r, 100));

    const calls = fetchMock.mock.calls as unknown[][];
    // Filter for `/api/tickets` but exclude `/api/tickets/:id/...` sub-paths if any.
    const ticketListCalls = calls.filter((c) => {
      const u = String(c[0]);
      return /\/api\/tickets(\?|$)/.test(u);
    });
    expect(ticketListCalls, `default-filter 漏发 fetch: ${JSON.stringify(ticketListCalls.map((c) => c[0]))}`).toHaveLength(0);
  });

  it("currentRunId='run-y' + default filters → fetch URL 必含 run_id=run-y", async () => {
    const RUN_ID = "run-y";
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: RUN_ID, state: "running" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;

    render(<TicketStreamPage />, { wrapper: Wrapper });

    await new Promise((r) => setTimeout(r, 100));

    const calls = fetchMock.mock.calls as unknown[][];
    const ticketCall = calls.find((c) => /\/api\/tickets(\?|$)/.test(String(c[0])));
    expect(ticketCall, `tickets fetch missing; calls=${JSON.stringify(calls.map((c) => c[0]))}`).toBeTruthy();
    const url = String(ticketCall![0]);
    expect(url, `tickets URL missing run_id=${RUN_ID}: ${url}`).toMatch(
      new RegExp(`run_id=${RUN_ID}`),
    );
  });
});
