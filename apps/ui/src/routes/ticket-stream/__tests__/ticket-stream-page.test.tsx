/**
 * TicketStreamPage —— 三栏 layout / 筛选 URL 同步 / event tree DOM / inline search / auto-scroll
 *
 * Traces To 特性 21 design §Interface Contract `TicketStreamPage` ·
 *           §Test Inventory T23 / T24 / T27 / T35 / T36 / T43 ·
 *           SRS FR-034 AC-1（筛选）+ AC-2（折叠展开）+ IFR-001（/ws/stream/:ticket_id）。
 *
 * Red 阶段：`apps/ui/src/routes/ticket-stream/index.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「筛选未应用 → 全部 ticket 渲染」→ T23 FAIL
 *   - 「event tree 一次性渲染所有 DOM 节点（无虚拟）」→ Perf 测试在 perf.test.ts 单独覆盖
 *   - 「Ctrl/Cmd+F 不 preventDefault」→ T36 FAIL
 *
 * [unit] —— uses fetch + WebSocket mocks; integration via test_f21_real_websocket.py.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act, fireEvent, waitFor } from "@testing-library/react";
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

function Wrapper({
  initial,
  children,
}: {
  initial: string;
  children: React.ReactNode;
}): React.ReactElement {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>{children}</MemoryRouter>
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

describe("TicketStreamPage 三栏 layout (T23/T24)", () => {
  it("T23 URL ?tool=claude → fetch 含 tool=claude param 且 ticket-list 仅 4 条 claude", async () => {
    // F24 B2 — TicketStream 现在需要 currentRunId 才会发 /api/tickets。
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
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
            { id: "t-1", state: "running", tool: "claude", skill: "design", events: 10 },
            { id: "t-2", state: "completed", tool: "claude", skill: "tdd", events: 5 },
            { id: "t-3", state: "running", tool: "claude", skill: "ucd", events: 1 },
            { id: "t-4", state: "completed", tool: "claude", skill: "ats", events: 0 },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    globalThis.fetch = fetchMock;
    const { container } = render(
      <Wrapper initial="/ticket-stream?tool=claude">
        <TicketStreamPage />
      </Wrapper>,
    );
    await waitFor(() => {
      const list = container.querySelector('[data-component="ticket-list"]');
      expect(list).not.toBeNull();
      expect(
        list!.querySelectorAll('[data-component="ticket-card"][data-tool="claude"]').length,
      ).toBe(4);
    });
    // URL 同步：fetch 至少有一次调用 URL 包含 tool=claude
    const calls = (fetchMock.mock.calls as unknown[][]).map((c) => String(c[0]));
    expect(calls.some((u) => u.includes("tool=claude"))).toBe(true);
  });

  it("T23b 三栏 selector 全部存在", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { container } = render(
      <Wrapper initial="/ticket-stream">
        <TicketStreamPage />
      </Wrapper>,
    );
    await waitFor(() => {
      expect(container.querySelector('[data-component="ticket-list"]')).not.toBeNull();
    });
    expect(container.querySelector('[data-component="event-tree"]')).not.toBeNull();
    expect(container.querySelector('[data-component="event-inspector"]')).not.toBeNull();
  });
});

describe("TicketStreamPage event tree 渲染 (T24/T27)", () => {
  it("T27 INTG/ws —— /ws/stream/:ticket_id 推 1 条 tool_use → DOM 末尾新增 row", async () => {
    globalThis.fetch = vi
      .fn()
      // /api/tickets
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([{ id: "t-1", state: "running", tool: "claude", skill: "design" }]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      // /api/tickets/t-1/stream historical
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    globalThis.fetch = vi.fn();
    let callIdx = 0;
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string | URL) => {
      const u = String(url);
      callIdx += 1;
      if (u.includes("/stream"))
        return Promise.resolve(
          new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      return Promise.resolve(
        new Response(
          JSON.stringify([{ id: "t-1", state: "running", tool: "claude", skill: "design" }]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    const { container } = render(
      <Wrapper initial="/ticket-stream?ticket=t-1">
        <TicketStreamPage />
      </Wrapper>,
    );
    await waitFor(() => {
      expect(container.querySelector('[data-component="event-tree"]')).not.toBeNull();
    });
    // F24 B3 — useWs 直连 /ws/stream/t-1 的 socket 是最后创建的实例。
    const ch = wsInstances[wsInstances.length - 1];
    act(() => {
      ch?._fireOpen();
      ch?._fireMessage({
        kind: "stream_event",
        channel: "/ws/stream/t-1",
        payload: { seq: 1, kind: "tool_use", payload: { name: "Bash" } },
      });
    });
    await waitFor(() => {
      const rows = container.querySelectorAll('[data-component="event-tree"] [data-row-index]');
      expect(rows.length).toBeGreaterThanOrEqual(1);
    });
  });
});

describe("TicketStreamPage Ctrl/Cmd+F 内联搜索 (T36)", () => {
  it("T36 Cmd+F 触发 → search input 聚焦 + preventDefault 阻止浏览器原生 find", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { container } = render(
      <Wrapper initial="/ticket-stream">
        <TicketStreamPage />
      </Wrapper>,
    );
    await waitFor(() => {
      expect(container.querySelector('[data-component="event-tree"]')).not.toBeNull();
    });
    // 模拟 Cmd+F；preventDefault 必须被调
    const ev = new KeyboardEvent("keydown", {
      key: "f",
      metaKey: true,
      bubbles: true,
      cancelable: true,
    });
    let prevented = false;
    const origPrevent = ev.preventDefault.bind(ev);
    ev.preventDefault = () => {
      prevented = true;
      origPrevent();
    };
    act(() => {
      window.dispatchEvent(ev);
    });
    expect(prevented).toBe(true);
    // search 输入框获得焦点（通过 [data-testid='inline-search'] 标识）
    await waitFor(() => {
      const input = container.querySelector(
        '[data-testid="inline-search"]',
      ) as HTMLInputElement | null;
      expect(input).not.toBeNull();
      expect(document.activeElement === input).toBe(true);
    });
  });
});

describe("TicketStreamPage auto-scroll 暂停 (T35)", () => {
  it("T35 用户向上 wheel → [data-testid='auto-scroll-indicator'] 文本含 '已暂停'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { container } = render(
      <Wrapper initial="/ticket-stream">
        <TicketStreamPage />
      </Wrapper>,
    );
    await waitFor(() => {
      expect(container.querySelector('[data-testid="auto-scroll-indicator"]')).not.toBeNull();
    });
    const tree = container.querySelector('[data-component="event-tree"]') as HTMLElement;
    act(() => {
      // 模拟用户向上滚动（deltaY < 0）
      fireEvent.wheel(tree, { deltaY: -120 });
    });
    await waitFor(() => {
      const txt = container.querySelector('[data-testid="auto-scroll-indicator"]')?.textContent ?? "";
      expect(txt).toContain("已暂停");
    });
  });
});

describe("TicketStreamPage 历史 stream 加载 (T43 INTG/api)", () => {
  it("T43 选中 ticket 时调 GET /api/tickets/:id/stream 加载历史事件", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string | URL) => {
      const u = String(url);
      if (u.includes("/stream")) {
        const events = [
          { seq: 1, kind: "text", payload: { text: "hello" } },
          { seq: 2, kind: "tool_use", payload: { name: "Read" } },
        ];
        return Promise.resolve(
          new Response(JSON.stringify(events), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify([{ id: "t-1", state: "running", tool: "claude", skill: "design" }]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    globalThis.fetch = fetchMock;
    render(
      <Wrapper initial="/ticket-stream?ticket=t-1">
        <TicketStreamPage />
      </Wrapper>,
    );
    await waitFor(() => {
      const calls = (fetchMock.mock.calls as unknown[][]).map((c) => String(c[0]));
      expect(calls.some((u) => /\/api\/tickets\/t-1\/stream/.test(u))).toBe(true);
    });
  });
});
