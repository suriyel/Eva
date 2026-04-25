/**
 * useWsStatus —— 暴露 HarnessWsClient 当前 connection state 的 React hook
 *
 * Traces §Test Inventory T30（IFR-007 60s 静默重连状态序列）。
 *
 * F12 HarnessWsClient 已交付 onState 订阅；此 hook 仅 React-binding。
 *
 * 状态序列（典型）：
 *   connecting → open → reconnecting（heartbeat timeout）→ connecting → open
 *
 * 行为：
 *   - mount 立刻读取 client.state（不依赖 onState 首次回调）
 *   - 注册 onState listener；unmount 时清理
 *   - 暴露 'closed' | 'connecting' | 'open' | 'reconnecting'
 */
import { useEffect, useState } from "react";
import { HarnessWsClient, type WsConnectionState } from "@/ws/client";

export interface UseWsStatusResult {
  status: WsConnectionState;
}

export function useWsStatus(): UseWsStatusResult {
  const client = HarnessWsClient.singleton();
  const [status, setStatus] = useState<WsConnectionState>(client.state);

  useEffect(() => {
    setStatus(client.state);
    const unsub = client.onState((s) => setStatus(s));
    return () => {
      unsub();
    };
  }, [client]);

  return { status };
}
