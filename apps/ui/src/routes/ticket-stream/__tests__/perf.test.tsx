/**
 * Performance 基准测试 —— FR-034 PERF (10k events ≥30fps) + NFR-002 (p95 < 2s)
 *
 * Traces To 特性 21 design §Test Inventory T25 (PERF/scroll) / T26 (PERF/latency) ·
 *           §Implementation Summary 决策(4) 虚拟滚动 + Zustand slice 减 re-render。
 *
 * Red 阶段：EventTree / virtual scroller 尚未实现，期望 ImportError 或 DOM-not-found FAIL。
 *
 * 注：happy-dom 不模拟真实 layout/paint，FPS 测量受限。本文件用代理指标：
 *   - T25 代理：渲染 10k events 后 DOM 节点数 ≪ 10k（虚拟滚动证据）
 *   - T26 代理：100 个 ws push 后所有事件都进入 EventTree row model（reducer 不阻塞）
 * 真正的 FPS / latency 由 Playwright E2E（feature-st）覆盖；TDD Red 仅验证"虚拟化已启用 + 状态正确写入"。
 *
 * [unit] —— uses happy-dom + WS mock; full perf via Playwright.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HarnessWsClient } from "@/ws/client";
import { TicketStreamPage } from "@/routes/ticket-stream";

const originalFetch = globalThis.fetch;

type MockWs = {
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  send: (d: string) => void;
  close: () => void;
  _fireOpen: () => void;
  _fireMessage: (p: unknown) => void;
};
let wsInstances: MockWs[] = [];

function installFakeWebSocket(): void {
  wsInstances = [];
  globalThis.WebSocket = function (this: MockWs, _url: string) {
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.send = () => undefined;
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

describe("T25 PERF/scroll —— 10k 事件虚拟滚动证据", () => {
  it("注入 10k StreamEvent 后 event-tree 实际 DOM row 数 << 10k（虚拟化已启用）", async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string | URL) => {
      const u = String(url);
      if (u.includes("/stream")) {
        const events = Array.from({ length: 10_000 }, (_, i) => ({
          seq: i + 1,
          kind: "tool_use",
          payload: { name: "Read", index: i },
        }));
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
    const { container } = render(
      <Wrapper initial="/ticket-stream?ticket=t-1">
        <TicketStreamPage />
      </Wrapper>,
    );
    await waitFor(() => {
      expect(container.querySelector('[data-component="event-tree"]')).not.toBeNull();
    });
    // 虚拟滚动证据：DOM rows < 1000（远小于 10k）；此断言失败说明所有节点直挂 → 性能必崩
    await waitFor(() => {
      const rows = container.querySelectorAll(
        '[data-component="event-tree"] [data-row-index]',
      );
      // 期望 happy-dom 默认 viewport 下虚拟滚动只渲少量；阈值 1000 留宽容。
      expect(rows.length).toBeLessThan(1000);
      // 同时至少渲染 1 行（证明数据已加载）
      expect(rows.length).toBeGreaterThanOrEqual(1);
    });
  });
});

describe("T26 PERF/latency —— 100 个 ws push 全部进入 row model", () => {
  it("WS 推 100 条 stream_event 后，event-tree 内部 row count 累积 ≥ 100", async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string | URL) => {
      const u = String(url);
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
    act(() => {
      wsInstances[0]?._fireOpen();
      for (let i = 0; i < 100; i += 1) {
        wsInstances[0]?._fireMessage({
          kind: "stream_event",
          channel: "/ws/stream/t-1",
          payload: { seq: i + 1, kind: "text", payload: { text: `msg ${i}` } },
        });
      }
    });
    // 经由 [data-row-total] 暴露 row 模型总数（虚拟滚动下 DOM 节点不全挂载，但 total 计数应等于 100）
    await waitFor(() => {
      const tree = container.querySelector('[data-component="event-tree"]') as HTMLElement | null;
      const total = Number(tree?.getAttribute("data-row-total") ?? 0);
      expect(total).toBeGreaterThanOrEqual(100);
    });
  });
});
