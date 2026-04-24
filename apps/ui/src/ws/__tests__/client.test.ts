/**
 * HarnessWsClient 单元测试——追溯 §Interface Contract / §Design Alignment / §Implementation Summary
 *
 * SRS Trace: NFR-001（UI 响应 p95 < 500ms 基座义务 —— WebSocket 客户端不引入
 *   无谓 re-render，为 Playwright T34 稳定达成 p95 < 500ms 奠基）
 *
 * 覆盖 Test Inventory：
 *   T01 FUNC/happy  · connect → state closed→connecting→open（Traces To §DA state closed→connecting / connecting→open, §DA seq msg#1-2, NFR-001 基座）
 *   T02 FUNC/error  · connect(非 ws 回环) → TypeError（§IC Raises）
 *   T04 FUNC/error  · subscribe(非法 channel) → RangeError（§IC Raises + §DA seq msg#4）
 *   T05 BNDRY/edge  · 指数退避 1/2/4/8/16s 上限（§BC 指数退避 + §DA state reconnecting→connecting）
 *   T06 BNDRY/edge  · 心跳 60s 阈值（§BC 心跳窗口 + §DA state open→reconnecting via heartbeatMissed）
 *   T07 FUNC/happy  · disconnect → closed 态，不再调度重连（§DA state open→closed）
 *   T29 SEC/url-guard · connect("ws://attacker.com") 拒绝（NFR-007 基座）
 *   T39 BNDRY/edge  · reconnecting → disconnect → 立即 closed，setTimeout 取消（§DA state reconnecting→closed）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { HarnessWsClient } from "@/ws/client";

type MockWsInstance = {
  url: string;
  readyState: number;
  sent: string[];
  onopen: ((ev: Event) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  send: (data: string) => void;
  close: (code?: number) => void;
  _fireOpen: () => void;
  _fireClose: (code?: number) => void;
  _fireMessage: (payload: unknown) => void;
};

function installMockWebSocket(): { instances: MockWsInstance[] } {
  const instances: MockWsInstance[] = [];
  const ctor = vi.fn(function (this: MockWsInstance, url: string) {
    this.url = url;
    this.readyState = 0;
    this.sent = [];
    this.onopen = null;
    this.onclose = null;
    this.onerror = null;
    this.onmessage = null;
    this.send = (data: string) => {
      this.sent.push(data);
    };
    this.close = (_code?: number) => {
      this.readyState = 3;
      this.onclose?.({ code: _code ?? 1000, reason: "", wasClean: true } as CloseEvent);
    };
    this._fireOpen = () => {
      this.readyState = 1;
      this.onopen?.(new Event("open"));
    };
    this._fireClose = (code = 1006) => {
      this.readyState = 3;
      this.onclose?.({ code, reason: "drop", wasClean: false } as CloseEvent);
    };
    this._fireMessage = (payload: unknown) => {
      this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
    };
    instances.push(this);
  }) as unknown as typeof WebSocket;
  globalThis.WebSocket = ctor;
  return { instances };
}

describe("HarnessWsClient", () => {
  let mock: { instances: MockWsInstance[] };

  beforeEach(() => {
    vi.useFakeTimers();
    mock = installMockWebSocket();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("T01 connect 成功——状态机 closed → connecting → open", () => {
    const client = new HarnessWsClient();
    expect(client.state).toBe("closed");
    client.connect("ws://127.0.0.1:8765");
    expect(client.state).toBe("connecting");
    expect(mock.instances).toHaveLength(1);
    mock.instances[0]._fireOpen();
    expect(client.state).toBe("open");
  });

  it("T02 connect 非 ws:// 回环地址抛 TypeError", () => {
    const client = new HarnessWsClient();
    expect(() => client.connect("http://evil.com")).toThrow(TypeError);
    expect(mock.instances).toHaveLength(0);
    expect(client.state).toBe("closed");
  });

  it("T29 connect 非 loopback host 抛 TypeError（SEC/url-guard，NFR-007 基座）", () => {
    const client = new HarnessWsClient();
    expect(() => client.connect("ws://attacker.com")).toThrow(TypeError);
    expect(mock.instances).toHaveLength(0);
  });

  it("T04 subscribe 未知 channel 抛 RangeError，未向 socket 发送任何消息", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    expect(() =>
      client.subscribe("/ws/unknown" as unknown as "/ws/hil", () => undefined),
    ).toThrow(RangeError);
    expect(mock.instances[0].sent).toEqual([]);
  });

  it("T05 指数退避按 1/2/4/8/16s 调度，第 6 次起保持 16s", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();

    const expectedDelays = [1000, 2000, 4000, 8000, 16000, 16000];
    for (let attempt = 0; attempt < expectedDelays.length; attempt += 1) {
      const sockIdx = mock.instances.length - 1;
      mock.instances[sockIdx]._fireClose(1006);
      expect(client.state).toBe("reconnecting");
      const before = mock.instances.length;
      vi.advanceTimersByTime(expectedDelays[attempt] - 1);
      // 断言：在规定 delay-1ms 时不得发起新连接
      expect(mock.instances.length, `尚未到退避时间：attempt=${attempt}`).toBe(before);
      vi.advanceTimersByTime(2);
      expect(mock.instances.length, `退避到点发起新连接：attempt=${attempt}`).toBe(before + 1);
      mock.instances[mock.instances.length - 1]._fireOpen();
    }
  });

  it("T06 心跳 60s 阈值——59.9s 仍 open；60.1s 触发 reconnecting", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    mock.instances[0]._fireMessage({ kind: "ping" });
    vi.advanceTimersByTime(59_900);
    expect(client.state).toBe("open");
    vi.advanceTimersByTime(200);
    expect(client.state).toBe("reconnecting");
  });

  it("T07 disconnect 使 socket 关闭，处于 closed，订阅 handler 不再调用", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    const handler = vi.fn();
    const unsub = client.subscribe("/ws/hil", handler);
    expect(typeof unsub).toBe("function");
    client.disconnect();
    expect(client.state).toBe("closed");
    // 断言服务端此后推消息也不再进入 handler
    mock.instances[0]._fireMessage({ kind: "hil_question_opened", channel: "/ws/hil" });
    expect(handler).not.toHaveBeenCalled();
  });

  it("T39 reconnecting 中调 disconnect —— 立即 closed，setTimeout 被清除，不再发起新连接", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    mock.instances[0]._fireClose(1006);
    expect(client.state).toBe("reconnecting");
    const before = mock.instances.length;
    client.disconnect();
    expect(client.state).toBe("closed");
    vi.advanceTimersByTime(60_000);
    expect(mock.instances.length).toBe(before);
  });

  // -------------------------------------------------------------------
  // 补充测试：覆盖 onmessage JSON 解析失败 / handler 异常 swallow / onerror 分支 /
  // heartbeat 超时后 socket.close 抛错被 swallow 的分支。
  // Traces To §IC `HarnessWsClient.heartbeat$` Raises（未抛出）+ §DA seq msg#7 (close →
  // scheduleReconnect) + §IC `subscribe.handler` postcondition（消费方异常不影响
  // client 状态机）+ NFR-001 基座义务（handler 异常不触发多余 re-render）
  // -------------------------------------------------------------------
  it("onmessage 收到非 JSON —— 静默忽略，状态保持 open，后续订阅仍工作", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    // 构造非法 JSON payload 触发 catch 分支
    const badEvent = new MessageEvent("message", { data: "<<<not-json>>>" });
    expect(() => mock.instances[0].onmessage?.(badEvent)).not.toThrow();
    expect(client.state).toBe("open");

    // 后续合法事件路由到 handler 不受影响
    const handler = vi.fn();
    client.subscribe("/ws/hil", handler);
    mock.instances[0]._fireMessage({ kind: "hil_question_opened", channel: "/ws/hil" });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("subscribe handler 抛错 —— client 吞错，同 channel 其他 handler 仍被调", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    const bad = vi.fn(() => {
      throw new Error("consumer-bug");
    });
    const good = vi.fn();
    client.subscribe("/ws/hil", bad);
    client.subscribe("/ws/hil", good);
    // 推事件；不应抛到 client
    expect(() =>
      mock.instances[0]._fireMessage({ kind: "x", channel: "/ws/hil" }),
    ).not.toThrow();
    expect(bad).toHaveBeenCalledTimes(1);
    expect(good).toHaveBeenCalledTimes(1);
    expect(client.state).toBe("open");
  });

  it("onerror 回调被调用 —— 不切状态、后续 onclose 才触发 reconnect（§DA state machine）", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    expect(client.state).toBe("open");
    // 仅 onerror 不改状态
    mock.instances[0].onerror?.(new Event("error"));
    expect(client.state).toBe("open");
    // 随后 onclose 才进入 reconnecting
    mock.instances[0]._fireClose(1006);
    expect(client.state).toBe("reconnecting");
  });

  it("心跳超时后 socket.close 抛错 —— 被吞，仍进入 reconnecting", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    // 让 socket.close 抛错以触发 _resetHeartbeatTimer 内部 catch 分支
    mock.instances[0].close = (_code?: number) => {
      throw new Error("close-unexpectedly-failed");
    };
    // 无 ping 推送 → 60s 心跳超时
    expect(() => vi.advanceTimersByTime(60_001)).not.toThrow();
    // close 抛错但 client 仍进入 reconnecting 调度
    expect(client.state).toBe("reconnecting");
  });

  it("heartbeat 监听订阅 —— ping 时 ok；60s 无 ping 时 missed", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    const seen: string[] = [];
    const unsub = client.heartbeat$.subscribe((s) => seen.push(s));
    mock.instances[0]._fireMessage({ kind: "ping" });
    expect(seen).toContain("ok");
    vi.advanceTimersByTime(60_001);
    expect(seen).toContain("missed");
    unsub();
    // 退订后新一轮 ping 不再投递
    const beforeLen = seen.length;
    // 先进入新的 connecting 以避免已关闭 socket
    mock.instances[mock.instances.length - 1]._fireOpen?.();
    expect(seen.length).toBe(beforeLen);
  });

  it("onState 监听 —— state 变更被广播一次", () => {
    const client = new HarnessWsClient();
    const transitions: string[] = [];
    const unsub = client.onState((s) => transitions.push(s));
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    expect(transitions).toEqual(["connecting", "open"]);
    unsub();
    client.disconnect();
    // 退订后不再收到 closed 通知
    expect(transitions).toEqual(["connecting", "open"]);
  });

  it("重复 connect —— 关闭先前 socket，开启新连接（幂等分支）", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    expect(client.state).toBe("open");
    const before = mock.instances.length;
    // 第 2 次 connect —— 关闭旧 socket，重新建立
    client.connect("ws://127.0.0.1:8765");
    expect(mock.instances.length).toBe(before + 1);
    expect(client.state).toBe("connecting");
  });

  it("subscribe 非函数 handler —— 抛 TypeError", () => {
    const client = new HarnessWsClient();
    client.connect("ws://127.0.0.1:8765");
    mock.instances[0]._fireOpen();
    expect(() =>
      client.subscribe("/ws/hil", undefined as unknown as (ev: unknown) => void),
    ).toThrow(TypeError);
  });

  it("subscribe 空字符串 channel —— 抛 RangeError（非空前置条件）", () => {
    const client = new HarnessWsClient();
    expect(() => client.subscribe("", () => undefined)).toThrow(RangeError);
  });

  it("singleton() 返回同一实例；__resetSingletonForTests 后生成新实例", () => {
    const a = HarnessWsClient.singleton();
    const b = HarnessWsClient.singleton();
    expect(a).toBe(b);
    HarnessWsClient.__resetSingletonForTests();
    const c = HarnessWsClient.singleton();
    expect(c).not.toBe(a);
  });
});
