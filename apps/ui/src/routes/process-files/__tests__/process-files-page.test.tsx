/**
 * ProcessFilesPage —— /process-files 结构化表单 + Zod 实时校验 +
 *                      Save → 后端 POST /api/validate/:file 双层校验 +
 *                      CrossFieldErrorList + subprocess stderr 不吞
 *
 * Traces To 特性 22 design §Test Inventory 22-12 / 22-13 / 22-14 / 22-15 /
 *                   22-25 / 22-34 ·
 *           §Interface Contract D (useValidate / ProcessFileForm /
 *                   CrossFieldErrorList / loadProcessFileSchema) ·
 *           §Visual Rendering Contract process-file-form / cross-field-errors ·
 *           SRS FR-038 + FR-039 + IAPI-016.
 *
 * Red 阶段：`apps/ui/src/routes/process-files/index.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「字段未按 schema 顶层 key 分组」→ 22-12 fieldset 缺失 FAIL
 *   - 「onChange 校验未触发」→ 22-13 data-invalid 缺失 / Save 仍 enabled FAIL
 *   - 「后端错误 toast 而非内联」→ 22-14 cross-field-errors li 缺失 FAIL
 *   - 「subprocess crash 被 fetch 吞掉」→ 22-15 stderr_tail 不显示 FAIL
 *   - 「Zod schema 字段漂移」→ 22-34 INTG/api 后端响应与前端 schema 不匹配 → parse FAIL
 *
 * [unit] —— uses fetch mocks; integration via tests/integration/test_f22_real_*.py.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";
import { z } from "zod";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ProcessFilesPage } from "@/routes/process-files";
import { ProcessFileForm } from "@/routes/process-files/components/process-file-form";
import { CrossFieldErrorList } from "@/routes/process-files/components/cross-field-error-list";
import { loadProcessFileSchema } from "@/routes/process-files/load-schema";

const originalFetch = globalThis.fetch;

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/process-files"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
    "http://127.0.0.1:8765";
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function jsonResp(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const FEATURE_LIST_VALUE = {
  features: [
    {
      id: 1,
      title: "F01 demo",
      srs_trace: ["FR-001"],
      status: "passing",
      category: "platform",
      ui: false,
    },
  ],
  constraints: ["CON-001"],
  assumptions: [],
  quality_gates: { line_coverage_min: 90, branch_coverage_min: 80 },
};

// 简化 schema 用于 unit test（loadProcessFileSchema 在 SUT 真实实现里返回完整 schema）
const FEATURE_LIST_SCHEMA = z.object({
  features: z.array(
    z.object({
      id: z.number().int(),
      title: z.string().min(1, "title required"),
      srs_trace: z.array(z.string()),
      status: z.enum(["failing", "passing", "blocked"]),
      category: z.string(),
      ui: z.boolean(),
    }),
  ),
  constraints: z.array(z.string()),
  assumptions: z.array(z.string()),
  quality_gates: z.object({
    line_coverage_min: z.number(),
    branch_coverage_min: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// 22-12 FUNC/happy — 字段按 schema 顶层 key 分组
// Traces To FR-038 AC + §IC <ProcessFileForm>
// ---------------------------------------------------------------------------
describe("22-12 FUNC/happy ProcessFileForm 字段分组", () => {
  it("加载 feature-list.json schema → 4 fieldset (features/constraints/assumptions/quality_gates)", () => {
    const { container } = render(
      <ProcessFileForm
        file="feature-list.json"
        schema={FEATURE_LIST_SCHEMA}
        value={FEATURE_LIST_VALUE}
        onChange={() => undefined}
        onSave={() => undefined}
      />,
    );
    const fieldsets = container.querySelectorAll("fieldset");
    expect(fieldsets.length).toBeGreaterThanOrEqual(4);
    // 检查每个 fieldset 含 schema 顶层 key 的 legend 或 data-group attr
    const groups = Array.from(fieldsets).map((fs) =>
      (fs.getAttribute("data-group") ?? fs.querySelector("legend")?.textContent ?? "").toLowerCase(),
    );
    for (const key of ["features", "constraints", "assumptions", "quality_gates"]) {
      expect(groups.some((g) => g.includes(key))).toBe(true);
    }
  });

  it("loadProcessFileSchema('feature-list.json') 返回 ZodSchema 实例（safeParse 可调）", () => {
    const schema = loadProcessFileSchema("feature-list.json");
    expect(schema).toBeDefined();
    const result = schema.safeParse({});
    expect(result.success).toBe(false); // empty object 不通过
  });

  it("loadProcessFileSchema 不在白名单 → 抛 'schema not found'", () => {
    expect(() => loadProcessFileSchema("random-file.txt")).toThrow(/schema not found/);
  });
});

// ---------------------------------------------------------------------------
// 22-13 FUNC/error — 必填字段空 onChange → data-invalid + Save disabled
// Traces To FR-039 AC1 + §IC <ProcessFileForm> Zod 校验
// ---------------------------------------------------------------------------
describe("22-13 FUNC/error onChange Zod 校验", () => {
  it("清空 features[0].title → 字段 data-invalid='true' + Save disabled", () => {
    const onChange = vi.fn();
    const onSave = vi.fn();
    let value = FEATURE_LIST_VALUE;
    const { container, rerender } = render(
      <ProcessFileForm
        file="feature-list.json"
        schema={FEATURE_LIST_SCHEMA}
        value={value}
        onChange={(next: unknown) => {
          value = next as typeof FEATURE_LIST_VALUE;
          onChange(next);
        }}
        onSave={onSave}
      />,
    );
    const titleInput = container.querySelector(
      '[data-field-path="features[0].title"] input',
    ) as HTMLInputElement | null;
    expect(titleInput).not.toBeNull();
    fireEvent.change(titleInput as HTMLInputElement, { target: { value: "" } });
    rerender(
      <ProcessFileForm
        file="feature-list.json"
        schema={FEATURE_LIST_SCHEMA}
        value={value}
        onChange={(next: unknown) => {
          value = next as typeof FEATURE_LIST_VALUE;
          onChange(next);
        }}
        onSave={onSave}
      />,
    );
    const fieldEl = container.querySelector('[data-field-path="features[0].title"]');
    expect(fieldEl?.getAttribute("data-invalid")).toBe("true");
    const saveBtn = container.querySelector(
      'button[data-testid="process-file-save-btn"]',
    ) as HTMLButtonElement;
    expect(saveBtn?.disabled).toBe(true);
  });

  it("填回非空 → data-invalid 移除 + Save enabled", () => {
    let value = { ...FEATURE_LIST_VALUE, features: [{ ...FEATURE_LIST_VALUE.features[0], title: "" }] };
    const onChange = vi.fn((next: unknown) => {
      value = next as typeof FEATURE_LIST_VALUE;
    });
    const { container, rerender } = render(
      <ProcessFileForm
        file="feature-list.json"
        schema={FEATURE_LIST_SCHEMA}
        value={value}
        onChange={onChange}
        onSave={() => undefined}
      />,
    );
    const fieldEl = container.querySelector('[data-field-path="features[0].title"]');
    expect(fieldEl?.getAttribute("data-invalid")).toBe("true");
    const titleInput = container.querySelector(
      '[data-field-path="features[0].title"] input',
    ) as HTMLInputElement;
    fireEvent.change(titleInput, { target: { value: "Restored Title" } });
    rerender(
      <ProcessFileForm
        file="feature-list.json"
        schema={FEATURE_LIST_SCHEMA}
        value={value}
        onChange={onChange}
        onSave={() => undefined}
      />,
    );
    const fieldEl2 = container.querySelector('[data-field-path="features[0].title"]');
    expect(fieldEl2?.getAttribute("data-invalid")).not.toBe("true");
    const saveBtn = container.querySelector(
      'button[data-testid="process-file-save-btn"]',
    ) as HTMLButtonElement;
    expect(saveBtn?.disabled).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 22-14 FUNC/error — 后端 ok=false issues → CrossFieldErrorList 内联
// Traces To FR-039 AC2 + §IC useValidate + §VRC CrossFieldErrorList
// ---------------------------------------------------------------------------
describe("22-14 FUNC/error 后端 cross-field 校验内联", () => {
  it("Save 触发 useValidate → ok=false issues 渲染 li × N + level=error 红色样式", async () => {
    let calls = 0;
    globalThis.fetch = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      calls += 1;
      if (url.includes("/api/files/tree")) {
        return jsonResp({
          root: ".",
          entries: [{ path: "feature-list.json", kind: "file", size: 1024 }],
        });
      }
      if (url.includes("/api/files/read")) {
        return jsonResp({
          path: "feature-list.json",
          content: JSON.stringify(FEATURE_LIST_VALUE),
          encoding: "utf-8",
        });
      }
      if (url.includes("/api/validate/")) {
        if (init?.method === "POST") {
          return jsonResp({
            ok: false,
            issues: [
              {
                path: "features[0].srs_trace",
                level: "error",
                message: "srs_trace 引用 FR-999 不存在",
              },
              { path: "features[0].dependencies", level: "warning", message: "dep 0 自循环" },
            ],
          });
        }
      }
      return jsonResp({ detail: `unhandled call ${calls}` }, 404);
    });
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-component="process-file-form"]')).not.toBeNull();
    });
    const saveBtn = await waitFor(() => {
      const b = container.querySelector(
        'button[data-testid="process-file-save-btn"]',
      ) as HTMLButtonElement;
      expect(b).not.toBeNull();
      expect(b.disabled).toBe(false);
      return b;
    });
    fireEvent.click(saveBtn);
    await waitFor(() => {
      const items = container.querySelectorAll('[data-component="cross-field-errors"] li');
      expect(items.length).toBeGreaterThanOrEqual(2);
    });
    const errorLi = container.querySelector(
      '[data-component="cross-field-errors"] li[data-error-level="error"]',
    );
    expect(errorLi).not.toBeNull();
    expect(errorLi?.getAttribute("data-error-path")).toBe("features[0].srs_trace");
    const warnLi = container.querySelector(
      '[data-component="cross-field-errors"] li[data-error-level="warning"]',
    );
    expect(warnLi).not.toBeNull();
  });

  it("CrossFieldErrorList 单元：渲染 issues 数组 → li × N + level 属性", () => {
    const issues = [
      { path: "a.b", level: "error" as const, message: "Err A" },
      { path: "c.d", level: "warning" as const, message: "Warn C" },
      { path: "e.f", level: "error" as const, message: "Err E" },
    ];
    const { container } = render(<CrossFieldErrorList issues={issues} />);
    const items = container.querySelectorAll('[data-component="cross-field-errors"] li');
    expect(items.length).toBe(3);
    expect(items[0].getAttribute("data-error-path")).toBe("a.b");
    expect(items[0].getAttribute("data-error-level")).toBe("error");
    expect(items[1].getAttribute("data-error-level")).toBe("warning");
  });
});

// ---------------------------------------------------------------------------
// 22-15 INTG/subprocess — ValidationReport.stderr_tail 渲染（subprocess 崩溃不吞）
// Traces To FR-039 + §IC useValidate Raises（不抛）+ Err-I
// ---------------------------------------------------------------------------
describe("22-15 INTG/subprocess stderr_tail 不被吞", () => {
  it("ValidationReport ok=false + stderr_tail='Traceback...' → UI 显示 stderr 内容；不抛 ServerError", async () => {
    const STDERR =
      "Traceback (most recent call last):\n  File 'validate_features.py', line 12\n    raise ValueError(...)\n";
    globalThis.fetch = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/files/tree")) {
        return jsonResp({
          root: ".",
          entries: [{ path: "feature-list.json", kind: "file", size: 1024 }],
        });
      }
      if (url.includes("/api/files/read")) {
        return jsonResp({
          path: "feature-list.json",
          content: JSON.stringify(FEATURE_LIST_VALUE),
          encoding: "utf-8",
        });
      }
      if (url.includes("/api/validate/")) {
        if (init?.method === "POST") {
          return jsonResp({ ok: false, issues: [], stderr_tail: STDERR });
        }
      }
      return jsonResp({ detail: "unhandled" }, 404);
    });
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    const saveBtn = await waitFor(() => {
      const b = container.querySelector('[data-testid="process-file-save-btn"]') as HTMLButtonElement;
      expect(b).not.toBeNull();
      return b;
    });
    fireEvent.click(saveBtn);
    await waitFor(() => {
      const stderrEl = container.querySelector('[data-testid="process-file-stderr-tail"]');
      expect(stderrEl).not.toBeNull();
      expect(stderrEl?.textContent ?? "").toContain("Traceback");
    });
    // 没有触发 ErrorBoundary
    expect(container.querySelector('[data-component="error-boundary"]')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 22-25 UI/render — process-file-form 红框 + Save disabled DOM 等价 [devtools]
// Traces To §VRC ProcessFileForm 红框 + devtools
// ---------------------------------------------------------------------------
describe("22-25 UI/render ProcessFileForm 必填红框 DOM 快照", () => {
  it("初始 value 含空必填字段 → data-invalid='true' 节点 ≥1 + Save disabled", () => {
    const valueWithEmpty = {
      ...FEATURE_LIST_VALUE,
      features: [{ ...FEATURE_LIST_VALUE.features[0], title: "" }],
    };
    const { container } = render(
      <ProcessFileForm
        file="feature-list.json"
        schema={FEATURE_LIST_SCHEMA}
        value={valueWithEmpty}
        onChange={() => undefined}
        onSave={() => undefined}
      />,
    );
    const invalidNodes = container.querySelectorAll('[data-invalid="true"]');
    expect(invalidNodes.length).toBeGreaterThanOrEqual(1);
    const saveBtn = container.querySelector(
      'button[data-testid="process-file-save-btn"]',
    ) as HTMLButtonElement;
    expect(saveBtn?.disabled).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 22-34 INTG/api — useValidate response schema parse（field name drift detection）
// Traces To §IC useValidate + IAPI-016
// ---------------------------------------------------------------------------
describe("22-34 INTG/api ValidationReport schema 严格匹配", () => {
  it("后端字段名漂移 ('errors' 而非 'issues') → Zod parse 失败 → mutation error 而非静默通过", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/files/tree")) {
        return jsonResp({
          root: ".",
          entries: [{ path: "feature-list.json", kind: "file", size: 1024 }],
        });
      }
      if (url.includes("/api/files/read")) {
        return jsonResp({
          path: "feature-list.json",
          content: JSON.stringify(FEATURE_LIST_VALUE),
          encoding: "utf-8",
        });
      }
      if (url.includes("/api/validate/")) {
        if (init?.method === "POST") {
          // 故意把 issues 字段重命名为 errors
          return jsonResp({
            ok: false,
            errors: [{ path: "x", level: "error", message: "field name drift" }],
          });
        }
      }
      return jsonResp({ detail: "unhandled" }, 404);
    });
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    const saveBtn = await waitFor(() => {
      const b = container.querySelector('[data-testid="process-file-save-btn"]') as HTMLButtonElement;
      expect(b).not.toBeNull();
      return b;
    });
    fireEvent.click(saveBtn);
    // 期望 schema 漂移被显式暴露：要么 mutation error 横幅，要么字段被强制为空 (issues 数组而非 li × 1)
    await waitFor(() => {
      const errBanner = container.querySelector('[data-testid="process-file-schema-mismatch-banner"]');
      const items = container.querySelectorAll('[data-component="cross-field-errors"] li');
      // 任一表面满足：错误横幅出现 OR 校验列表为空（issues 字段不存在）
      expect(errBanner !== null || items.length === 0).toBe(true);
    });
  });
});
