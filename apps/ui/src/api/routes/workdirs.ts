/**
 * Workspace 管理 hooks — /api/workdirs.
 *
 * - useWorkdirs       GET   /api/workdirs
 * - useSelectWorkdir  POST  /api/workdirs/select { path }
 * - useRemoveWorkdir  POST  /api/workdirs/remove { path }
 * - pickNativeWorkdir POST  /api/workdirs/pick-native (无 webview 时返回 501)
 */
import { createApiHook, HttpError } from "../query-hook-factory";
import { resolveApiBaseUrl } from "../client";
import {
  workdirStateSchema,
  workdirSelectRequestSchema,
  workdirPickNativeResponseSchema,
} from "../../lib/zod-schemas";

export const useWorkdirs = createApiHook({
  method: "GET",
  path: "/api/workdirs",
  responseSchema: workdirStateSchema,
});

export const useSelectWorkdir = createApiHook({
  method: "POST",
  path: "/api/workdirs/select",
  requestSchema: workdirSelectRequestSchema,
  responseSchema: workdirStateSchema,
});

export const useRemoveWorkdir = createApiHook({
  method: "POST",
  path: "/api/workdirs/remove",
  requestSchema: workdirSelectRequestSchema,
  responseSchema: workdirStateSchema,
});

/**
 * 调原生 FOLDER_DIALOG（仅桌面壳）。Web 模式 backend 返回 501，调用方应据此
 * fallback 到文本输入对话框。
 *
 * 返回值：
 *   - { ok: true, path: string }  用户选了一个目录
 *   - { ok: true, path: null }    用户取消
 *   - { ok: false, code: 'not_supported_in_web_mode' }   501 (Web 模式)
 */
export type PickNativeOutcome =
  | { ok: true; path: string | null }
  | { ok: false; code: string };

export async function pickNativeWorkdir(): Promise<PickNativeOutcome> {
  const resp = await fetch(`${resolveApiBaseUrl()}/api/workdirs/pick-native`, {
    method: "POST",
  });
  if (resp.status === 501) {
    let code = "not_supported_in_web_mode";
    try {
      const body = (await resp.json()) as { detail?: { error_code?: string } };
      if (body?.detail?.error_code) code = body.detail.error_code;
    } catch {
      /* ignore parse errors */
    }
    return { ok: false, code };
  }
  if (!resp.ok) {
    throw new HttpError(resp.status, await resp.text());
  }
  const raw = (await resp.json()) as unknown;
  const parsed = workdirPickNativeResponseSchema.parse(raw);
  return { ok: true, path: parsed.path };
}
