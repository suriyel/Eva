/**
 * apiClient.fetch 测试——T08 FUNC/error
 * Traces To §IC apiClient.fetch · §IS §4 契约集成 · §BC boundary
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiClient, ServerError, HttpError, NetworkError } from "@/api/client";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  // 注入 base URL（§IC precondition）
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ = "http://127.0.0.1:8765";
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("apiClient.fetch", () => {
  it("T08 5xx 响应拒绝为 ServerError 且携带 status:500", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "boom" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiClient.fetch("GET", "/api/foo")).rejects.toSatisfy((err: unknown) => {
      // 断言：必须是 ServerError 且 status 精确为 500，且 detail 可读
      return (
        err instanceof ServerError &&
        (err as ServerError).status === 500 &&
        typeof (err as ServerError).detail === "string"
      );
    });
  });

  // ------------------------------------------------------------------
  // 补充测试：覆盖 4xx HttpError.code 提取 + NetworkError 路径 + 非 JSON body
  // Traces To §IC apiClient.fetch Raises 行（HttpError / NetworkError）+ §IS §4 契约
  // "错误归一：HttpError.code 使用 FastAPI 返回的 detail.code"。
  // ------------------------------------------------------------------
  it("4xx 响应含 {detail:{code:...}} —— HttpError.code 提取为嵌套 code 字符串", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: { code: "run_already_running", msg: "x" } }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiClient.fetch("POST", "/api/runs", { id: 1 })).rejects.toSatisfy(
      (err: unknown) => {
        return (
          err instanceof HttpError &&
          (err as HttpError).status === 409 &&
          (err as HttpError).code === "run_already_running"
        );
      },
    );
  });

  it("4xx 响应 detail 缺 code —— HttpError.code 回退为 null", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "not_found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiClient.fetch("GET", "/api/missing")).rejects.toSatisfy((err: unknown) => {
      return (
        err instanceof HttpError &&
        (err as HttpError).status === 404 &&
        (err as HttpError).code === null
      );
    });
  });

  it("fetch 本身抛出（网络失败）—— 包装为 NetworkError 且保留原 message", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    await expect(apiClient.fetch("GET", "/api/x")).rejects.toSatisfy((err: unknown) => {
      return err instanceof NetworkError && /ECONNREFUSED/.test((err as Error).message);
    });
  });

  it("fetch 抛出非 Error 对象 —— NetworkError.message 退化为 String(e)", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue("raw-string-failure");
    await expect(apiClient.fetch("GET", "/api/y")).rejects.toSatisfy((err: unknown) => {
      return err instanceof NetworkError && (err as Error).message === "raw-string-failure";
    });
  });

  it("5xx 响应 body 是裸字符串 —— ServerError.detail 原样透传（stringifyServerDetail string 分支）", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("plain text server failure", { status: 503 }),
    );
    await expect(apiClient.fetch("GET", "/api/z")).rejects.toSatisfy((err: unknown) => {
      return (
        err instanceof ServerError &&
        (err as ServerError).status === 503 &&
        (err as ServerError).detail === "plain text server failure"
      );
    });
  });

  it("5xx 响应 body 是非 record 数组 —— ServerError.detail JSON.stringify fallback", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([1, 2, 3]), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiClient.fetch("GET", "/api/arr")).rejects.toSatisfy((err: unknown) => {
      return (
        err instanceof ServerError &&
        (err as ServerError).detail === "[1,2,3]"
      );
    });
  });

  it("2xx 响应为空 body —— fetch 返回 null（parseJsonSafe 空串分支）", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("", { status: 200 }),
    );
    const result = await apiClient.fetch<unknown>("GET", "/api/ok");
    expect(result).toBeNull();
  });

  it("2xx 响应含非 JSON body —— fetch 返回原始字符串（parseJsonSafe fallback 分支）", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("not-json-at-all", { status: 200 }),
    );
    const result = await apiClient.fetch<unknown>("GET", "/api/text");
    expect(result).toBe("not-json-at-all");
  });
});
