/**
 * submitHilAnswer —— IAPI-002 POST /api/hil/:ticket_id/answer 包装
 *
 * Traces To 特性 21 design §Interface Contract `submitHilAnswer` Raises ·
 *           §Test Inventory T17 / T19 / T20 / T21 / T22 / T39 / T40 ·
 *           SRS FR-031 AC-2 + SEC（freeform XSS payload literal）·
 *           Boundary Conditions freeform_text.length ≤ 2000。
 *
 * Red 阶段：`submit.ts` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「不区分 404/409/400 → 一律抛 generic Error」→ T20/T21/T22 FAIL
 *   - 「忽略 freeform_text length」→ T39 客户端 disable 校验 FAIL
 *   - 「freeform_text 用模板拼接进 URL/body 字符串」→ T17/T40 字面量回显 FAIL
 *
 * [unit] —— uses fetch mock (apiClient internal); pure transport/error layer.
 *           A real-WS smoke (real_http) lives in tests/integration/test_f21_real_ws.py.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  submitHilAnswer,
  HilSubmitError,
  validateFreeformLength,
  HIL_FREEFORM_MAX,
} from "@/routes/hil-inbox/submit";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
    "http://127.0.0.1:8765";
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("submitHilAnswer 路径 + body schema (T19 INTG/api)", () => {
  it("T19 POST /api/hil/:ticket_id/answer —— URL/method/body 精确匹配契约", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ accepted: true, ticket_state: "running" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;

    const ack = await submitHilAnswer("t-42", {
      question_id: "q-1",
      selected_labels: ["A"],
      freeform_text: null,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8765/api/hil/t-42/answer");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });
    const body = JSON.parse(String(init?.body));
    expect(body).toEqual({
      question_id: "q-1",
      selected_labels: ["A"],
      freeform_text: null,
    });
    expect(ack).toEqual({ accepted: true, ticket_state: "running" });
  });
});

describe("submitHilAnswer 错误码分类 (Raises)", () => {
  it("T20 HTTP 404 → HilSubmitError code='TICKET_NOT_FOUND'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "ticket missing" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(
      submitHilAnswer("t-x", { question_id: "q-1", selected_labels: null, freeform_text: null }),
    ).rejects.toSatisfy((e: unknown) => e instanceof HilSubmitError && e.code === "TICKET_NOT_FOUND");
  });

  it("T21 HTTP 409 → HilSubmitError code='STATE_CONFLICT'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "not in hil_waiting" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(
      submitHilAnswer("t-1", { question_id: "q-1", selected_labels: null, freeform_text: null }),
    ).rejects.toSatisfy((e: unknown) => e instanceof HilSubmitError && e.code === "STATE_CONFLICT");
  });

  it("T22 HTTP 400 → HilSubmitError code='BAD_REQUEST' 且 detail 透传", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "freeform_text too long" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );
    let captured: HilSubmitError | null = null;
    try {
      await submitHilAnswer("t-1", {
        question_id: "q-1",
        selected_labels: null,
        freeform_text: null,
      });
    } catch (e) {
      captured = e as HilSubmitError;
    }
    expect(captured).toBeInstanceOf(HilSubmitError);
    expect(captured!.code).toBe("BAD_REQUEST");
    // detail 透传到 message 或 detail 字段（用户可读）
    expect(JSON.stringify(captured)).toContain("freeform_text too long");
  });
});

describe("freeform_text 长度边界 (T39 BNDRY/edge)", () => {
  it("HIL_FREEFORM_MAX 被声明为 2000（与 UCD §4.2 prototype 计数器一致）", () => {
    expect(HIL_FREEFORM_MAX).toBe(2000);
  });

  it("T39 freeform_text=2001 chars → validateFreeformLength 返回 false（客户端 disable 提交）", () => {
    const text = "a".repeat(2001);
    expect(validateFreeformLength(text)).toBe(false);
  });

  it("T39b freeform_text=2000 chars → validateFreeformLength 返回 true（边界包含）", () => {
    const text = "a".repeat(2000);
    expect(validateFreeformLength(text)).toBe(true);
  });

  it("T39c freeform_text=null → validateFreeformLength 返回 true（空/缺省合法）", () => {
    expect(validateFreeformLength(null)).toBe(true);
  });

  it("T39d FUNC/error —— freeform_text>2000 chars 通过校验失败时 submit 必须不发出请求", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ accepted: true, ticket_state: "running" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;
    const oversize = "a".repeat(2001);
    let captured: Error | null = null;
    try {
      await submitHilAnswer("t-1", {
        question_id: "q-1",
        selected_labels: null,
        freeform_text: oversize,
      });
    } catch (e) {
      captured = e as Error;
    }
    // 抛错且不调 fetch（客户端预校验拦截）
    expect(captured).toBeInstanceOf(HilSubmitError);
    expect((captured as HilSubmitError).code).toBe("BAD_REQUEST");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("submitHilAnswer 网络异常 (FUNC/error · NetworkError)", () => {
  it("fetch 抛 TypeError → submit 抛 HilSubmitError code='NETWORK_ERROR'", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    let captured: HilSubmitError | null = null;
    try {
      await submitHilAnswer("t-1", {
        question_id: "q-1",
        selected_labels: null,
        freeform_text: null,
      });
    } catch (e) {
      captured = e as HilSubmitError;
    }
    expect(captured).toBeInstanceOf(HilSubmitError);
    expect(captured!.code).toBe("NETWORK_ERROR");
  });
});

describe("freeform XSS 字面量回显 (T17/T40 SEC/xss)", () => {
  it("T17 提交 body.freeform_text 是字符串字面量 —— 不做模板拼接 / 不调 innerHTML", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ accepted: true, ticket_state: "running" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;
    const xss = "<img src=x onerror=alert(1)>";
    await submitHilAnswer("t-1", {
      question_id: "q-1",
      selected_labels: null,
      freeform_text: xss,
    });
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(String(init?.body));
    // 关键断言：body.freeform_text 必须等于原文（不被 escape，也不被改写）
    expect(body.freeform_text).toBe(xss);
    // 不出现于 URL 路径中（防止被错误拼到 ticket id）
    const urlStr = String(fetchMock.mock.calls[0][0]);
    expect(urlStr).toBe("http://127.0.0.1:8765/api/hil/t-1/answer");
  });

  it("T40 freeform_text 含中文方括号片段 `[FR-010]` —— body 字面量保留", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ accepted: true, ticket_state: "running" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;
    const text = "Hello [FR-010]";
    await submitHilAnswer("t-1", {
      question_id: "q-1",
      selected_labels: null,
      freeform_text: text,
    });
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body.freeform_text).toBe(text);
  });
});
