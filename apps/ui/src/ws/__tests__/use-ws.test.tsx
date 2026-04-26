/**
 * useWs hook 测试——T11 FUNC/happy · T12 FUNC/error (cleanup)
 * Traces To §IC useWs · §DA seq msg#3/6 · F24 §IS B3 (per-channel client)
 *
 * SRS Trace: NFR-001（UI 响应 p95 < 500ms 基座义务 —— useWs 订阅/清理不触发
 *   多余 re-render，为 Playwright T34 p95 < 500ms 奠基）
 *
 * Update for F24 B3:
 *   useWs now creates its own per-channel HarnessWsClient instance instead
 *   of consuming a singleton that was pre-connected at the root path. The
 *   single WebSocket instance observed in the test is the per-channel socket
 *   created by the hook itself; pre-connecting the singleton no longer
 *   dictates the hook's state.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, act } from "@testing-library/react";
import * as React from "react";
import { useWs } from "@/ws/use-ws";
import { HarnessWsClient } from "@/ws/client";

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

let instances: MockWs[] = [];
beforeEach(() => {
  instances = [];
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
    this._fireMessage = (payload: unknown) => {
      this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
    };
    instances.push(this);
  } as unknown as typeof WebSocket;
});

function Probe(props: { onEvent: (ev: unknown) => void; children?: (status: string) => React.ReactNode }) {
  const { status } = useWs("/ws/hil", props.onEvent);
  return <div data-testid="status">{status}</div>;
}

describe("useWs", () => {
  beforeEach(() => {
    HarnessWsClient.__resetSingletonForTests?.();
    (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
      "http://127.0.0.1:8765";
  });

  it("T11 mount 订阅、事件到达时 handler 被调，status 从 connecting → open", () => {
    const onEvent = vi.fn();
    const { getByTestId } = render(<Probe onEvent={onEvent} />);
    // F24 B3: hook 直连 /ws/hil → 1 个 WebSocket 实例。
    expect(instances.length).toBeGreaterThanOrEqual(1);
    const channelWs = instances[instances.length - 1];
    // 初始 status === "connecting"
    expect(getByTestId("status").textContent).toBe("connecting");
    act(() => {
      channelWs._fireOpen();
    });
    expect(getByTestId("status").textContent).toBe("open");
    act(() => {
      channelWs._fireMessage({
        kind: "hil_question_opened",
        channel: "/ws/hil",
      });
    });
    expect(onEvent).toHaveBeenCalledTimes(1);
  });

  it("T12 unmount 后 handler 不再被调（cleanup 退订）", () => {
    const onEvent = vi.fn();
    const { unmount } = render(<Probe onEvent={onEvent} />);
    const channelWs = instances[instances.length - 1];
    act(() => {
      channelWs._fireOpen();
    });
    unmount();
    act(() => {
      channelWs._fireMessage({
        kind: "hil_question_opened",
        channel: "/ws/hil",
      });
    });
    expect(onEvent).not.toHaveBeenCalled();
  });
});
