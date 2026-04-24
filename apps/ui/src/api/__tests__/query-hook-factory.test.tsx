/**
 * createApiHook 测试——T09 FUNC/error · T10 BNDRY/edge · T40 FUNC/happy · T41 FUNC/error
 * Traces To §IC createApiHook · §BC route.path · §IC apiClient
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import * as React from "react";
import { z } from "zod";
import { createApiHook, HttpError } from "@/api/query-hook-factory";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ = "http://127.0.0.1:8765";
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("createApiHook", () => {
  it("T10 路径不以 /api/ 开头——直接抛 Error", () => {
    expect(() =>
      createApiHook({ method: "GET", path: "/foo", responseSchema: z.unknown() }),
    ).toThrow(/\/api\//);
  });

  it("T09 响应 schema 不匹配——hook 抛 ZodError", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "abc" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const useFoo = createApiHook({
      method: "GET",
      path: "/api/foo",
      responseSchema: z.object({ id: z.number() }),
    });
    const { result } = renderHook(() => useFoo({}), { wrapper: wrapper() });
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    // 断言：error 是 ZodError（而非 generic Error），验证 schema 真被执行
    expect(result.current.error?.name).toBe("ZodError");
  });

  it("T40 GET /api/health —— TanStack useQuery 数据经 Zod 解析成功", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ bind: "127.0.0.1", version: "0.0.1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const useHealth = createApiHook({
      method: "GET",
      path: "/api/health",
      responseSchema: z.object({ bind: z.string(), version: z.string() }),
    });
    const { result } = renderHook(() => useHealth({}), { wrapper: wrapper() });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toEqual({ bind: "127.0.0.1", version: "0.0.1" });
  });

  it("Mutation 无 requestSchema —— 跳过 parse，直接调用 fetch（分支 L81 requestSchema 缺省）", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const useDelete = createApiHook({
      method: "DELETE",
      path: "/api/runs/r-1",
      responseSchema: z.object({ ok: z.literal(true) }),
    });
    const { result } = renderHook(() => useDelete({}), { wrapper: wrapper() });
    let value: unknown;
    await act(async () => {
      value = await result.current.mutateAsync(undefined as never);
    });
    expect(value).toEqual({ ok: true });
  });

  it("T41 Mutation 收到 409 —— onError 被触发，error 为 HttpError{status:409, code}", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: { code: "run_already_running" } }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const useStartRun = createApiHook({
      method: "POST",
      path: "/api/runs",
      requestSchema: z.object({ id: z.string() }),
      responseSchema: z.object({ ok: z.literal(true) }),
    });
    const onError = vi.fn();
    const { result } = renderHook(() => useStartRun({ onError }), { wrapper: wrapper() });
    await act(async () => {
      try {
        await result.current.mutateAsync({ id: "r-1" });
      } catch {
        // expected
      }
    });
    await waitFor(() => {
      expect(onError).toHaveBeenCalled();
    });
    const err = onError.mock.calls[0][0];
    expect(err).toBeInstanceOf(HttpError);
    expect(err.status).toBe(409);
    expect(err.code).toBe("run_already_running");
  });
});
