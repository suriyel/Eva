/**
 * WebSocket 60s 静默自动重连 (T30 INTG/recon · IFR-007)
 *
 * Traces To 特性 21 design §Test Inventory T30 ·
 *           SRS IFR-007（60s 未收消息 → 重连）·
 *           §Visual Rendering Contract ws-status 短暂闪 reconnecting → connected。
 *
 * Red 阶段：F12 已实现 HarnessWsClient 基础重连逻辑（heartbeat 60s 超时 → close → reconnect），
 * 但 F21 期望额外 ui-binding：ws-status 状态可被订阅且在 page 中作为 [data-testid='ws-status'] 暴露。
 * 该 hook `useWsStatus` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「不订阅 onState」→ status 永远停在 'connecting'
 *   - 「heartbeat 超时不进 reconnecting 状态」→ T30 状态序列断言 FAIL
 *
 * [unit] —— uses fake timers + WS mock; integration WS test in tests/integration.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { HarnessWsClient } from "@/ws/client";
import { useWsStatus } from "@/routes/ticket-stream/use-ws-status";

type MockWs = {
  onopen: ((ev: Event) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  send: (d: string) => void;
  close: (code?: number) => void;
  _fireOpen: () => void;
  _fireClose: () => void;
};
let wsInstances: MockWs[] = [];

function installFakeWebSocket(): void {
  wsInstances = [];
  globalThis.WebSocket = function (this: MockWs, _url: string) {
    this.onopen = null;
    this.onclose = null;
    this.onmessage = null;
    this.send = () => undefined;
    this.close = () => {
      this.onclose?.(new CloseEvent("close"));
    };
    this._fireOpen = () => {
      this.onopen?.(new Event("open"));
    };
    this._fireClose = () => {
      this.onclose?.(new CloseEvent("close"));
    };
    wsInstances.push(this);
  } as unknown as typeof WebSocket;
}

beforeEach(() => {
  vi.useFakeTimers();
  installFakeWebSocket();
  HarnessWsClient.__resetSingletonForTests();
});

afterEach(() => {
  vi.useRealTimers();
  HarnessWsClient.__resetSingletonForTests();
});

describe("useWsStatus + 60s heartbeat reconnect (T30 IFR-007)", () => {
  it("T30 connecting → open → reconnecting → connecting → open 状态序列被 hook 暴露", () => {
    const client = HarnessWsClient.singleton();
    client.connect("ws://127.0.0.1:8765");
    const { result } = renderHook(() => useWsStatus());
    expect(result.current.status).toBe("connecting");
    act(() => {
      wsInstances[0]?._fireOpen();
    });
    expect(result.current.status).toBe("open");

    // 推进 60s 静默 → heartbeat 超时 → close → reconnecting
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(result.current.status).toBe("reconnecting");

    // 推进 backoff 1s → 重新打开 socket（新实例）
    act(() => {
      vi.advanceTimersByTime(1_000);
    });
    expect(wsInstances.length).toBeGreaterThanOrEqual(2);
    act(() => {
      wsInstances[wsInstances.length - 1]?._fireOpen();
    });
    expect(result.current.status).toBe("open");
  });

  it("T30b 用户主动 disconnect → 状态变 closed，不再重连（即使 heartbeat 超时）", () => {
    const client = HarnessWsClient.singleton();
    client.connect("ws://127.0.0.1:8765");
    const { result } = renderHook(() => useWsStatus());
    act(() => {
      wsInstances[0]?._fireOpen();
    });
    expect(result.current.status).toBe("open");
    act(() => {
      client.disconnect();
    });
    expect(result.current.status).toBe("closed");
    // 推进时间不应再重连
    act(() => {
      vi.advanceTimersByTime(120_000);
    });
    // wsInstances 长度不增（最多还是 1）
    expect(wsInstances.length).toBe(1);
  });
});
