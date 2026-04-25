/**
 * submitHilAnswer —— IAPI-002 POST /api/hil/:ticket_id/answer 包装
 *
 * Traces §Interface Contract `submitHilAnswer` Raises ·
 *        Boundary Conditions freeform_text.length ≤ 2000。
 *
 * 错误码归一：
 *   - HTTP 400 → BAD_REQUEST（detail 透传）
 *   - HTTP 404 → TICKET_NOT_FOUND
 *   - HTTP 409 → STATE_CONFLICT
 *   - 其他 4xx → BAD_REQUEST（默认归集）
 *   - fetch 抛 TypeError / 网络异常 → NETWORK_ERROR
 *
 * SEC：freeform_text 经 JSON.stringify 进 body，URL 路径仅含 ticketId（无字符串拼接 / 无模板插值）。
 */
import { resolveApiBaseUrl } from "@/api/client";

export const HIL_FREEFORM_MAX = 2000;

export type HilSubmitErrorCode =
  | "BAD_REQUEST"
  | "TICKET_NOT_FOUND"
  | "STATE_CONFLICT"
  | "NETWORK_ERROR";

export interface HilAnswerSubmit {
  question_id: string;
  selected_labels: string[] | null;
  freeform_text: string | null;
}

export interface HilAnswerAck {
  accepted: boolean;
  ticket_state: string;
}

export class HilSubmitError extends Error {
  public readonly code: HilSubmitErrorCode;
  public readonly status: number | null;
  public readonly detail: unknown;

  constructor(
    code: HilSubmitErrorCode,
    message: string,
    status: number | null = null,
    detail: unknown = null,
  ) {
    super(message);
    this.name = "HilSubmitError";
    this.code = code;
    this.status = status;
    this.detail = detail;
    Object.setPrototypeOf(this, HilSubmitError.prototype);
  }

  // include code+detail in JSON.stringify so test assertions can grep by string content
  toJSON(): Record<string, unknown> {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      status: this.status,
      detail: this.detail,
    };
  }
}

export function validateFreeformLength(text: string | null): boolean {
  if (text == null) return true;
  return text.length <= HIL_FREEFORM_MAX;
}

function statusToCode(status: number): HilSubmitErrorCode {
  if (status === 404) return "TICKET_NOT_FOUND";
  if (status === 409) return "STATE_CONFLICT";
  return "BAD_REQUEST";
}

async function parseDetail(resp: Response): Promise<unknown> {
  try {
    const text = await resp.text();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  } catch {
    return null;
  }
}

export async function submitHilAnswer(
  ticketId: string,
  body: HilAnswerSubmit,
): Promise<HilAnswerAck> {
  if (typeof ticketId !== "string" || ticketId.length === 0) {
    throw new HilSubmitError("BAD_REQUEST", "ticketId must be non-empty");
  }
  if (!body || typeof body.question_id !== "string" || body.question_id.length === 0) {
    throw new HilSubmitError("BAD_REQUEST", "question_id must be non-empty");
  }
  if (!validateFreeformLength(body.freeform_text)) {
    throw new HilSubmitError(
      "BAD_REQUEST",
      `freeform_text exceeds ${HIL_FREEFORM_MAX} chars`,
    );
  }

  const base = resolveApiBaseUrl();
  const url = `${base}/api/hil/${ticketId}/answer`;

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new HilSubmitError(
      "NETWORK_ERROR",
      e instanceof Error ? e.message : String(e),
    );
  }

  if (resp.status >= 400) {
    const detail = await parseDetail(resp);
    const code = statusToCode(resp.status);
    const detailStr =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "detail" in (detail as Record<string, unknown>)
          ? String((detail as Record<string, unknown>).detail)
          : JSON.stringify(detail);
    throw new HilSubmitError(code, `HTTP ${resp.status}: ${detailStr}`, resp.status, detail);
  }

  const text = await resp.text();
  const ack = text ? (JSON.parse(text) as HilAnswerAck) : ({} as HilAnswerAck);
  return ack;
}
