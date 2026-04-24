/**
 * HarnessWsClient — F12 基座 WebSocket client (IAPI-001 consumer).
 * §4 Interface Contract / §6 Implementation Summary / state machine §4 are authoritative.
 */

export type WsChannelPattern =
  | "/ws/run/:id"
  | "/ws/stream/:ticket_id"
  | "/ws/hil"
  | "/ws/anomaly"
  | "/ws/signal";

export type WsConnectionState = "closed" | "connecting" | "open" | "reconnecting";

export interface WsEvent {
  kind: string;
  channel?: string;
  payload?: unknown;
}

export type WsHandler = (ev: WsEvent) => void;
export type Unsubscribe = () => void;

const ALLOWED_CHANNEL_PATTERNS: RegExp[] = [
  /^\/ws\/run\/[^/]+$/,
  /^\/ws\/stream\/[^/]+$/,
  /^\/ws\/hil$/,
  /^\/ws\/anomaly$/,
  /^\/ws\/signal$/,
];

const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000] as const;
const HEARTBEAT_TIMEOUT_MS = 60_000;

function isLoopbackWsUrl(url: string): boolean {
  if (typeof url !== "string" || url.length === 0) return false;
  return url.startsWith("ws://127.0.0.1:") || url.startsWith("ws://localhost:");
}

function validateChannel(channel: string): void {
  if (typeof channel !== "string" || channel.length === 0) {
    throw new RangeError("channel must be a non-empty string");
  }
  const ok = ALLOWED_CHANNEL_PATTERNS.some((re) => re.test(channel));
  if (!ok) {
    throw new RangeError(`channel not in whitelist: ${channel}`);
  }
}

type HeartbeatListener = (status: "ok" | "missed") => void;

export class HarnessWsClient {
  private static _singleton: HarnessWsClient | null = null;

  public static singleton(): HarnessWsClient {
    if (!HarnessWsClient._singleton) {
      HarnessWsClient._singleton = new HarnessWsClient();
    }
    return HarnessWsClient._singleton;
  }

  /** test helper — reset cached singleton between cases. */
  public static __resetSingletonForTests(): void {
    HarnessWsClient._singleton = null;
  }

  private _state: WsConnectionState = "closed";
  private _url: string | null = null;
  private _socket: WebSocket | null = null;
  private _handlers = new Map<string, Set<WsHandler>>();
  private _attempt = 0;
  private _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
  private _heartbeatListeners = new Set<HeartbeatListener>();
  private _stateListeners = new Set<(s: WsConnectionState) => void>();
  // user-requested disconnect blocks all reconnect attempts.
  private _userClosed = false;

  public get state(): WsConnectionState {
    return this._state;
  }

  public readonly heartbeat$ = {
    subscribe: (listener: HeartbeatListener): Unsubscribe => {
      this._heartbeatListeners.add(listener);
      return () => {
        this._heartbeatListeners.delete(listener);
      };
    },
  };

  public onState(listener: (s: WsConnectionState) => void): Unsubscribe {
    this._stateListeners.add(listener);
    return () => {
      this._stateListeners.delete(listener);
    };
  }

  public connect(url: string): void {
    if (!isLoopbackWsUrl(url)) {
      throw new TypeError(
        `HarnessWsClient.connect: URL must be ws://127.0.0.1:<port> or ws://localhost:<port> (got ${String(url)})`,
      );
    }
    // Re-connect idempotently: close stale socket (if any) and start fresh connecting attempt.
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._heartbeatTimer) {
      clearTimeout(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
    if (this._socket && (this._state === "open" || this._state === "connecting")) {
      const prev = this._socket;
      this._socket = null;
      try {
        prev.onclose = null;
        prev.onopen = null;
        prev.onmessage = null;
        prev.onerror = null;
        prev.close();
      } catch {
        /* ignore */
      }
    }
    this._userClosed = false;
    this._url = url;
    this._attempt = 0;
    this._openSocket();
  }

  public disconnect(): void {
    this._userClosed = true;
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._heartbeatTimer) {
      clearTimeout(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
    if (this._socket) {
      try {
        this._socket.close(1000);
      } catch {
        /* ignore */
      }
      this._socket = null;
    }
    this._setState("closed");
  }

  public subscribe(channel: string, handler: WsHandler): Unsubscribe {
    validateChannel(channel);
    if (typeof handler !== "function") {
      throw new TypeError("handler must be a function");
    }
    let set = this._handlers.get(channel);
    const firstSubscriber = !set || set.size === 0;
    if (!set) {
      set = new Set<WsHandler>();
      this._handlers.set(channel, set);
    }
    set.add(handler);
    if (firstSubscriber) {
      this._send({ kind: "subscribe", channel });
    }
    return () => {
      const cur = this._handlers.get(channel);
      if (!cur) return;
      cur.delete(handler);
      if (cur.size === 0) {
        this._handlers.delete(channel);
        this._send({ kind: "unsubscribe", channel });
      }
    };
  }

  // ----- internal -----

  private _setState(next: WsConnectionState): void {
    if (this._state !== next) {
      this._state = next;
      for (const l of this._stateListeners) {
        try {
          l(next);
        } catch {
          /* swallow listener errors */
        }
      }
    }
  }

  private _send(msg: unknown): void {
    if (!this._socket) return;
    // Only send when socket is open; otherwise drop (will be re-sent on next open for subscribes).
    try {
      this._socket.send(JSON.stringify(msg));
    } catch {
      /* ignore */
    }
  }

  private _openSocket(): void {
    if (!this._url) return;
    this._setState("connecting");
    const sock = new WebSocket(this._url);
    this._socket = sock;
    sock.onopen = () => {
      this._setState("open");
      this._resetHeartbeatTimer();
      // re-subscribe all known channels.
      for (const ch of this._handlers.keys()) {
        this._send({ kind: "subscribe", channel: ch });
      }
    };
    sock.onmessage = (ev: MessageEvent) => {
      if (this._userClosed) return;
      let data: WsEvent | null = null;
      try {
        data = JSON.parse(String(ev.data)) as WsEvent;
      } catch {
        return;
      }
      if (!data || typeof data !== "object") return;
      if (data.kind === "ping") {
        this._resetHeartbeatTimer();
        for (const l of this._heartbeatListeners) l("ok");
        return;
      }
      if (typeof data.channel === "string") {
        const handlers = this._handlers.get(data.channel);
        if (handlers) {
          for (const h of handlers) {
            try {
              h(data);
            } catch {
              /* swallow consumer errors */
            }
          }
        }
      }
    };
    sock.onerror = () => {
      // onclose is expected to follow; state transition handled there.
    };
    sock.onclose = () => {
      if (this._heartbeatTimer) {
        clearTimeout(this._heartbeatTimer);
        this._heartbeatTimer = null;
      }
      if (this._userClosed) {
        this._setState("closed");
        return;
      }
      this._scheduleReconnect();
    };
  }

  private _scheduleReconnect(): void {
    this._setState("reconnecting");
    const idx = Math.min(this._attempt, BACKOFF_MS.length - 1);
    const delay = BACKOFF_MS[idx];
    this._attempt += 1;
    if (this._reconnectTimer) clearTimeout(this._reconnectTimer);
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      if (this._userClosed) return;
      this._openSocket();
    }, delay);
  }

  private _resetHeartbeatTimer(): void {
    if (this._heartbeatTimer) clearTimeout(this._heartbeatTimer);
    this._heartbeatTimer = setTimeout(() => {
      this._heartbeatTimer = null;
      for (const l of this._heartbeatListeners) l("missed");
      // heartbeat miss → enter reconnecting
      if (this._socket) {
        try {
          this._socket.close(4001);
        } catch {
          /* ignore */
        }
      }
      if (!this._userClosed) {
        this._scheduleReconnect();
      }
    }, HEARTBEAT_TIMEOUT_MS);
  }
}
