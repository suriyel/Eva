/**
 * Feature #24 B3 — WebSocket 5 路径直连 (path-per-channel) — no root multiplex.
 *
 * Traces To
 * =========
 *   B3-P1  IAPI-001 §6.2.3 5 path / IFR-007 / VRC B3                 INTG/ws
 *   B3-N1  §IC `useWs` Raises (RangeError on invalid channel)        FUNC/error
 *   B3-N2  §6.1.7 心跳重连 (single channel error doesn't kill others) INTG/ws
 *   B3-P2  §VRC TicketStream WS chip — covered by ticket-stream tests
 *   §Design Alignment seq msg#1..#4 (mount → connect → upgrade → 101 per channel)
 *   §Implementation Summary B3 (per-channel HarnessWsClient instance, no singleton root)
 *
 * Rule 4 wrong-impl challenge:
 *   - 「WebSocket(`ws://host:port/`) 一次 + subscribe 帧路由」     → B3-P1 fail
 *   - 「全 5 channel 共享单例 socket」                              → B3-P1 fail (5 ctor calls)
 *   - 「白名单旁路 (`/ws/invalid` 接受)」                          → B3-N1 fail
 *   - 「单连断线导致全 5 channel 进 reconnecting」                 → B3-N2 fail
 *
 * Rule 5 layer:
 *   [unit] uses MockWebSocket; SUT useWs + HarnessWsClient real.
 *   Real test for end-to-end 5-channel handshake against uvicorn lives in
 *   tests/integration/test_f23_real_uvicorn_handshake.py.
 *
 * Red 阶段：当前 useWs 用 `HarnessWsClient.singleton()` 共享单实例 + AppShell
 *   `client.connect(resolveWsBase())` 连根路径。挂载 5 channel → WebSocket
 *   构造函数仍在根 URL 调用 1 次（subscribe 帧多路复用）。
 *   B3-P1 断言「ctor 调用 5 次 + URL 各为 5 channel 路径」直接 FAIL。
 *
 * Feature ref: feature 24
 *
 * [unit] — uses MockWebSocket.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act } from "@testing-library/react";
import * as React from "react";
import { useWs } from "@/ws/use-ws";
import { HarnessWsClient } from "@/ws/client";

type MockWs = {
  url: string;
  sent: string[];
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  readyState: number;
  send: (d: string) => void;
  close: () => void;
  _fireOpen: () => void;
  _fireError: () => void;
  _fireClose: () => void;
};

let instances: MockWs[] = [];

function installFakeWebSocket(): void {
  instances = [];
  // CONNECTING=0 OPEN=1 CLOSING=2 CLOSED=3
  globalThis.WebSocket = function (this: MockWs, url: string) {
    this.url = url;
    this.sent = [];
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
    this.readyState = 0;
    this.send = (d: string) => {
      this.sent.push(d);
    };
    this.close = () => {
      this.readyState = 3;
      this.onclose?.(new CloseEvent("close"));
    };
    this._fireOpen = () => {
      this.readyState = 1;
      this.onopen?.(new Event("open"));
    };
    this._fireError = () => {
      this.onerror?.(new Event("error"));
    };
    this._fireClose = () => {
      this.readyState = 3;
      this.onclose?.(new CloseEvent("close"));
    };
    instances.push(this);
  } as unknown as typeof WebSocket;
}

beforeEach(() => {
  installFakeWebSocket();
  HarnessWsClient.__resetSingletonForTests?.();
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
    "http://127.0.0.1:8765";
});

afterEach(() => {
  vi.restoreAllMocks();
});

function MultiChannelProbe(): React.ReactElement {
  const noop = React.useCallback(() => undefined, []);
  useWs("/ws/run/r1", noop);
  useWs("/ws/stream/t1", noop);
  useWs("/ws/hil", noop);
  useWs("/ws/anomaly", noop);
  useWs("/ws/signal", noop);
  return <div />;
}

// --------------------------------------------------------------------- B3-P1
describe("B3-P1 INTG/ws — 5 channels each open WebSocket directly to its path", () => {
  it("挂载 5 useWs → globalThis.WebSocket ctor 调用 5 次 + URL 各为 5 channel 路径 + 0 次根路径调用", () => {
    render(<MultiChannelProbe />);
    // After mount, each channel must produce its own WebSocket instance.
    expect(instances.length, `ctor 调用次数应为 5，实际 ${instances.length}`).toBe(5);
    const urls = instances.map((i) => i.url).sort();
    const expected = [
      "ws://127.0.0.1:8765/ws/anomaly",
      "ws://127.0.0.1:8765/ws/hil",
      "ws://127.0.0.1:8765/ws/run/r1",
      "ws://127.0.0.1:8765/ws/signal",
      "ws://127.0.0.1:8765/ws/stream/t1",
    ];
    expect(urls).toEqual(expected);
    // No root-path connection.
    const rootHits = urls.filter((u) => u === "ws://127.0.0.1:8765/" || u === "ws://127.0.0.1:8765");
    expect(rootHits, `root-path WS connection observed: ${rootHits.join(",")}`).toHaveLength(0);
  });
});

// --------------------------------------------------------------------- B3-N1
describe("B3-N1 FUNC/error — useWs throws RangeError on invalid channel", () => {
  it("useWs('/ws/invalid') → 抛 RangeError 且不创建 WebSocket 实例", () => {
    function BadProbe(): React.ReactElement {
      // Bypass type guard: cast to any.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      useWs("/ws/invalid" as any, () => undefined);
      return <div />;
    }
    // Suppress React error noise.
    const origErr = console.error;
    console.error = () => undefined;
    try {
      let caught: unknown = null;
      try {
        render(<BadProbe />);
      } catch (e) {
        caught = e;
      }
      expect(caught, "expected RangeError, got nothing").not.toBeNull();
      expect((caught as Error).name).toMatch(/RangeError|TypeError/);
      // No WS instance created.
      expect(instances, `unexpected WS opened on invalid channel; urls=${instances.map((i) => i.url).join(",")}`).toHaveLength(0);
    } finally {
      console.error = origErr;
    }
  });
});

// --------------------------------------------------------------------- B3-N2
describe("B3-N2 INTG/ws — single channel close doesn't sever others", () => {
  it("/ws/hil 触 close → 仅 hil 进入 reconnecting；其余 4 channel 状态保持 open", () => {
    render(<MultiChannelProbe />);
    expect(instances.length, "expected 5 sockets").toBe(5);
    // Open all sockets.
    act(() => {
      for (const ws of instances) ws._fireOpen();
    });
    // Close only the hil socket.
    const hil = instances.find((i) => i.url.endsWith("/ws/hil"));
    expect(hil, "no hil socket").not.toBeUndefined();
    act(() => {
      hil!._fireClose();
    });
    // The remaining 4 sockets must still be readyState===1 (OPEN).
    const others = instances.filter((i) => !i.url.endsWith("/ws/hil"));
    for (const ws of others) {
      expect(ws.readyState, `${ws.url} unexpectedly closed (cascade): readyState=${ws.readyState}`).toBe(1);
    }
  });
});

// --------------------------------------------------------------------- B3-N3 (extra)
describe("B3-N3 FUNC/error — useWs MUST NOT connect to bare root path 'ws://host:port/'", () => {
  it("挂载 useWs('/ws/hil') 单 channel → WebSocket ctor URL 必含 '/ws/hil' 路径，绝不止于 host:port/", () => {
    function HilOnly(): React.ReactElement {
      useWs("/ws/hil", () => undefined);
      return <div />;
    }
    render(<HilOnly />);
    expect(instances.length, `expected 1 socket for /ws/hil, got ${instances.length}`).toBeGreaterThanOrEqual(1);
    const url = instances[0].url;
    // Must NOT be the bare root URL.
    expect(
      url === "ws://127.0.0.1:8765" || url === "ws://127.0.0.1:8765/",
      `WS URL is bare root path (B3 root-multiplex anti-pattern): ${url}`,
    ).toBe(false);
    // Must contain `/ws/hil` segment.
    expect(url, `WS URL missing /ws/hil channel path: ${url}`).toMatch(/\/ws\/hil$/);
  });
});

// --------------------------------------------------------------------- B3-extra (defensive)
describe("B3-extra — connect URL must end with channel path (HarnessWsClient.connect contract)", () => {
  it("HarnessWsClient.connect('ws://127.0.0.1:8765/ws/hil') accepts loopback URL with path", () => {
    const client = new HarnessWsClient();
    // Must not throw — current `isLoopbackWsUrl` accepts any path under loopback host.
    expect(() => client.connect("ws://127.0.0.1:8765/ws/hil")).not.toThrow();
    // Constructor should produce one ws instance with that exact URL.
    const last = instances[instances.length - 1];
    expect(last?.url, `last WS URL: ${last?.url}`).toBe("ws://127.0.0.1:8765/ws/hil");
  });
});
