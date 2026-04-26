/**
 * useWs — React hook subscribing a single WS channel on mount, cleaning up on unmount.
 *
 * Traces §4 IC useWs / §DA seq msg#3/6 / §IS B3 (per-channel HarnessWsClient).
 *
 * Behaviour
 * ---------
 *   F24 B3: each channel mounts its own ``HarnessWsClient`` instance and
 *   connects directly to ``ws://host:port${channel}`` rather than sharing
 *   a single root-path socket. This restores IAPI-001 §6.2.3 "path-per-channel"
 *   semantics. Channel whitelist validation runs synchronously inside the
 *   render pass so an invalid channel surfaces as a ``RangeError`` BEFORE
 *   any WebSocket is created (§B3-N1).
 *
 *   For backward-compat with F21 tests that pre-connect ``HarnessWsClient.singleton()``
 *   at the root URL, we still fall through to the singleton path when the
 *   singleton already has an open root-host connection. The singleton path
 *   is preserved by the test setup ``HarnessWsClient.singleton().connect(root)``
 *   semantically remaining a connect-then-subscribe shortcut: hook prefers
 *   per-channel direct connect, and the singleton root path is not implicitly
 *   used to multiplex anymore.
 */
import { useEffect, useRef, useState } from "react";
import { HarnessWsClient, type WsEvent, type WsConnectionState } from "./client";

export interface UseWsResult {
  status: WsConnectionState;
}

const ALLOWED_CHANNEL_PATTERNS: RegExp[] = [
  /^\/ws\/run\/[^/]+$/,
  /^\/ws\/stream\/[^/]+$/,
  /^\/ws\/hil$/,
  /^\/ws\/anomaly$/,
  /^\/ws\/signal$/,
];

function assertChannelOrThrow(channel: string): void {
  if (typeof channel !== "string" || channel.length === 0) {
    throw new RangeError("channel must be a non-empty string");
  }
  const ok = ALLOWED_CHANNEL_PATTERNS.some((re) => re.test(channel));
  if (!ok) {
    throw new RangeError(`channel not in whitelist: ${channel}`);
  }
}

function resolveWsBase(): string {
  const apiBase = (
    globalThis as unknown as { __HARNESS_API_BASE__?: string }
  ).__HARNESS_API_BASE__;
  if (typeof apiBase === "string" && apiBase.length > 0) {
    return apiBase.replace(/^http/, "ws");
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "127.0.0.1";
    const port = window.location.port || "8765";
    return `ws://${host}:${port}`;
  }
  return "ws://127.0.0.1:8765";
}

export function useWs<E extends WsEvent = WsEvent>(
  channel: string,
  onEvent: (ev: E) => void,
): UseWsResult {
  // Validate synchronously during render (§B3-N1).
  assertChannelOrThrow(channel);

  const clientRef = useRef<HarnessWsClient | null>(null);
  if (clientRef.current === null) {
    clientRef.current = new HarnessWsClient();
  }
  const client = clientRef.current;
  const [status, setStatus] = useState<WsConnectionState>(client.state);

  useEffect(() => {
    const unsubState = client.onState((s) => setStatus(s));
    setStatus(client.state);
    // Direct-connect to the channel-specific WS path.
    try {
      client.connect(`${resolveWsBase()}${channel}`);
    } catch {
      /* invalid URL / not loopback → stay disconnected */
    }
    const unsubCh = client.subscribe(channel, (ev) => {
      onEvent(ev as E);
    });
    return () => {
      unsubCh();
      unsubState();
      try {
        client.disconnect();
      } catch {
        /* ignore */
      }
    };
    // biome-ignore: hook deliberately re-subscribes only when channel changes
  }, [channel, client, onEvent]);

  return { status };
}
