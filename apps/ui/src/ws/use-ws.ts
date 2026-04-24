/**
 * useWs — React hook subscribing a single WS channel on mount, cleaning up on unmount.
 * Traces §4 IC useWs / §DA seq msg#3/6.
 */
import { useEffect, useState } from "react";
import { HarnessWsClient, type WsEvent, type WsConnectionState } from "./client";

export interface UseWsResult {
  status: WsConnectionState;
}

export function useWs<E extends WsEvent = WsEvent>(
  channel: string,
  onEvent: (ev: E) => void,
): UseWsResult {
  const client = HarnessWsClient.singleton();
  const [status, setStatus] = useState<WsConnectionState>(client.state);

  useEffect(() => {
    const unsubState = client.onState((s) => setStatus(s));
    setStatus(client.state);
    const unsubCh = client.subscribe(channel, (ev) => {
      onEvent(ev as E);
    });
    return () => {
      unsubCh();
      unsubState();
    };
    // biome-ignore: hook deliberately re-subscribes only when channel changes
  }, [channel, client, onEvent]);

  return { status };
}
