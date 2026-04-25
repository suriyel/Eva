/**
 * apiClient — F12 REST client (IAPI-002 consumer).
 * §4 Interface Contract apiClient.fetch authoritative.
 * Error normalization: 4xx → HttpError · 5xx → ServerError · network → NetworkError.
 */

export class HttpError extends Error {
  public readonly status: number;
  public readonly code: string | null;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, code: string | null = null) {
    super(`HTTP ${status}`);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export class ServerError extends Error {
  public readonly status: number;
  public readonly detail: string;
  constructor(status: number, detail: string) {
    super(`Server ${status}`);
    this.name = "ServerError";
    this.status = status;
    this.detail = detail;
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

interface EnvMeta {
  env?: { VITE_API_BASE?: string };
}

type ApiBaseHolder = { __HARNESS_API_BASE__?: unknown };

function readApiBase(obj: unknown): string | null {
  const raw = (obj as ApiBaseHolder | null | undefined)?.__HARNESS_API_BASE__;
  return typeof raw === "string" && raw.length > 0 ? raw : null;
}

/**
 * Resolve the REST API base URL.
 *
 * Priority: `globalThis.__HARNESS_API_BASE__` → `window.__HARNESS_API_BASE__`
 * → Vite `import.meta.env.VITE_API_BASE` → empty string (same-origin).
 *
 * Exported for direct `fetch()` callers (F21 routes) that bypass `apiClient`
 * for low-level streaming / control-flow paths but still need to resolve
 * the loopback host consistently.
 */
export function resolveApiBaseUrl(): string {
  const fromGlobal = readApiBase(globalThis);
  if (fromGlobal) return fromGlobal;
  if (typeof window !== "undefined") {
    const fromWindow = readApiBase(window);
    if (fromWindow) return fromWindow;
  }
  try {
    // import.meta.env is defined by Vite at build time.
    const meta = (import.meta as unknown as EnvMeta) ?? {};
    if (meta.env?.VITE_API_BASE) return meta.env.VITE_API_BASE;
  } catch {
    /* ignore */
  }
  return "";
}

async function parseJsonSafe(resp: Response): Promise<unknown> {
  const text = await resp.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object";
}

function stringifyServerDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (isRecord(detail) && "detail" in detail) return String(detail.detail);
  return JSON.stringify(detail);
}

function extractErrorCode(detail: unknown): string | null {
  if (!isRecord(detail)) return null;
  const inner = detail.detail;
  if (isRecord(inner) && "code" in inner) return String(inner.code);
  return null;
}

export const apiClient = {
  async fetch<Resp = unknown>(method: string, path: string, body?: unknown): Promise<Resp> {
    const base = resolveApiBaseUrl();
    const url = `${base}${path}`;
    let resp: Response;
    try {
      resp = await fetch(url, {
        method,
        headers: body != null ? { "Content-Type": "application/json" } : undefined,
        body: body != null ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new NetworkError(e instanceof Error ? e.message : String(e));
    }
    if (resp.status >= 500) {
      const detail = await parseJsonSafe(resp);
      throw new ServerError(resp.status, stringifyServerDetail(detail));
    }
    if (resp.status >= 400) {
      const detail = await parseJsonSafe(resp);
      throw new HttpError(resp.status, detail, extractErrorCode(detail));
    }
    return (await parseJsonSafe(resp)) as Resp;
  },
};
