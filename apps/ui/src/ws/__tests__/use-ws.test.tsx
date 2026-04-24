/**
 * useWs hook 测试——T11 FUNC/happy · T12 FUNC/error (cleanup)
 * Traces To §IC useWs · §DA seq msg#3/6
 *
 * SRS Trace: NFR-001（UI 响应 p95 < 500ms 基座义务 —— useWs 订阅/清理不触发
 *   多余 re-render，为 Playwright T34 p95 < 500ms 奠基）
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
  it("T11 mount 订阅、事件到达时 handler 被调，status 从 connecting → open", () => {
    // 使用全局单例模式（setup + connect）
    HarnessWsClient.singleton().connect("ws://127.0.0.1:8765");
    const onEvent = vi.fn();
    const { getByTestId } = render(<Probe onEvent={onEvent} />);
    // 初始 status === "connecting"
    expect(getByTestId("status").textContent).toBe("connecting");
    act(() => {
      instances[0]._fireOpen();
    });
    expect(getByTestId("status").textContent).toBe("open");
    act(() => {
      instances[0]._fireMessage({
        kind: "hil_question_opened",
        channel: "/ws/hil",
      });
    });
    expect(onEvent).toHaveBeenCalledTimes(1);
  });

  it("T12 unmount 后 handler 不再被调（cleanup 退订）", () => {
    HarnessWsClient.singleton().connect("ws://127.0.0.1:8765");
    const onEvent = vi.fn();
    const { unmount } = render(<Probe onEvent={onEvent} />);
    act(() => {
      instances[0]._fireOpen();
    });
    unmount();
    act(() => {
      instances[0]._fireMessage({
        kind: "hil_question_opened",
        channel: "/ws/hil",
      });
    });
    expect(onEvent).not.toHaveBeenCalled();
  });
});
