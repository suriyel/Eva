/**
 * HarnessWsClient.subscribe 正向路径——T03 FUNC/happy
 * Traces To §IC HarnessWsClient.subscribe · §DA seq msg#3 · §DA seq msg#6
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { HarnessWsClient } from "@/ws/client";

type MockWs = {
  sent: string[];
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  _fireOpen: () => void;
  _fireMessage: (payload: unknown) => void;
  close: (code?: number) => void;
  send: (data: string) => void;
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
    this.close = () => {
      this.onclose?.({ code: 1000, reason: "", wasClean: true } as CloseEvent);
    };
    this._fireOpen = () => {
      this.onopen?.(new Event("open"));
    };
    this._fireMessage = (payload: unknown) => {
      this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
    };
    instances.push(this);
  } as unknown as typeof WebSocket;
});

describe("HarnessWsClient.subscribe", () => {
  it("T03 首次订阅发 SubscribeMsg；服务端推事件后 handler 被调 1 次", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    instances[0]._fireOpen();
    const handler = vi.fn();
    const unsub = client.subscribe("/ws/hil", handler);

    // 断言：SubscribeMsg 已发送（JSON 包含 channel + kind:"subscribe"）
    expect(instances[0].sent.length).toBeGreaterThanOrEqual(1);
    const subMsg = JSON.parse(instances[0].sent[0]);
    expect(subMsg.kind).toBe("subscribe");
    expect(subMsg.channel).toBe("/ws/hil");

    // 服务端推事件 —— handler 正好被调一次且收到完整 payload
    instances[0]._fireMessage({
      kind: "hil_question_opened",
      channel: "/ws/hil",
      payload: { ticketId: "t-1", question: "继续？" },
    });
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler.mock.calls[0][0]).toMatchObject({
      kind: "hil_question_opened",
      channel: "/ws/hil",
    });

    // 退订后服务端再推同 channel 事件，handler 不再被调
    unsub();
    instances[0]._fireMessage({
      kind: "hil_question_opened",
      channel: "/ws/hil",
      payload: { ticketId: "t-2" },
    });
    expect(handler).toHaveBeenCalledTimes(1);

    // 断言：最后订阅者退订 → UnsubscribeMsg 发送
    const lastSent = JSON.parse(instances[0].sent[instances[0].sent.length - 1]);
    expect(lastSent.kind).toBe("unsubscribe");
    expect(lastSent.channel).toBe("/ws/hil");
  });
});
