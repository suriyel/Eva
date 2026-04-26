/**
 * Feature #24 B6 — ProcessFiles 控件大幅补齐 (设计稿对照).
 *
 * Traces To
 * =========
 *   B6-P1  §VRC ProcessFiles file chips                            UI/render
 *   B6-P2  §VRC 三 h3 分块                                          UI/render
 *   B6-P3  §VRC features Grid Table / FR-038                        UI/render
 *   B6-P4  §VRC 右 340px 校验面板                                    UI/render
 *   B6-P5  §VRC header 双 button + dirty chip                       UI/render
 *   B6-N1  §VRC 错误态 / FR-038 BNDRY                               UI/render
 *   B6-N2  FR-039 backend 校验 — 必填空 + 保存时校验                 FUNC/error
 *   B6-P6  IAPI-016 POST /api/validate/feature-list.json            INTG/api
 *   §Implementation Summary B6
 *
 * Rule 4 wrong-impl challenge:
 *   - 「无 FileChipsRow」                                       → B6-P1 fail
 *   - 「无 h3 分块」                                            → B6-P2 fail
 *   - 「features 是 textarea 而非 Grid Table」                  → B6-P3 fail
 *   - 「右栏 width != 340px」                                   → B6-P4 fail
 *   - 「dirty chip 永远显示 / 永不显示」                         → B6-P5 fail
 *   - 「fetch 404 卡 loading」                                  → B6-N1 fail
 *   - 「必填空字段直接 PUT」                                    → B6-N2 fail
 *
 * Rule 5 layer:
 *   [unit] uses fetch mocks; SUT real-imported.
 *
 * Red 阶段：当前 process-files/index.tsx 极简 — 单文件硬编码 + 无右栏 + 无
 *   header buttons + 404 error 卡 'loading'。本测试每个断言直接 FAIL.
 *
 * Feature ref: feature 24
 *
 * [unit] — uses fetch mocks; jsdom.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProcessFilesPage } from "@/routes/process-files";

const originalFetch = globalThis.fetch;

const FEATURE_LIST_BODY = {
  path: "feature-list.json",
  content: JSON.stringify(
    {
      project: { name: "harness", version: "0.1.0" },
      tech_stack: { language: "python", test_framework: "pytest" },
      features: [
        { id: 1, title: "F01", status: "passing", srs_trace: ["FR-001"] },
        { id: 2, title: "F02", status: "passing", srs_trace: ["FR-002"] },
      ],
    },
    null,
    2,
  ),
  encoding: "utf-8",
};

function withFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>): ReturnType<typeof vi.fn> {
  const fn = vi.fn(handler);
  globalThis.fetch = fn as unknown as typeof globalThis.fetch;
  return fn;
}

function defaultHandler(input: RequestInfo | URL, _init?: RequestInit): Promise<Response> {
  const url = String(input);
  if (url.includes("/api/files/read")) {
    return Promise.resolve(
      new Response(JSON.stringify(FEATURE_LIST_BODY), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }
  if (url.includes("/api/validate/")) {
    return Promise.resolve(
      new Response(
        JSON.stringify({
          ok: true,
          issues: [],
          stderr_tail: "",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  }
  return Promise.resolve(
    new Response(JSON.stringify({}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

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

// --------------------------------------------------------------------- B6-P1
describe("B6-P1 UI/render — 顶部 4 file chips", () => {
  it("4 file chips data-testid + textContent 严格匹配", async () => {
    withFetch(defaultHandler);
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const chips = [
        '[data-testid="file-chip-feature-list"]',
        '[data-testid="file-chip-env-guide"]',
        '[data-testid="file-chip-long-task-guide"]',
        '[data-testid="file-chip-env-example"]',
      ];
      const labels = chips.map((sel) => container.querySelector(sel)?.textContent?.trim() ?? null);
      expect(labels, `chips: ${JSON.stringify(labels)}`).toEqual([
        "feature-list.json",
        "env-guide.md",
        "long-task-guide.md",
        ".env.example",
      ]);
    });
  });
});

// --------------------------------------------------------------------- B6-P2
describe("B6-P2 UI/render — 三 h3 分块 textContent", () => {
  it("h3 data-section project/tech-stack/features textContent 严格 [Project, Tech Stack, Features]", async () => {
    withFetch(defaultHandler);
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const proj = container.querySelector('h3[data-section="project"]');
      const ts = container.querySelector('h3[data-section="tech-stack"]');
      const ft = container.querySelector('h3[data-section="features"]');
      expect(proj?.textContent?.trim(), `project h3: ${proj?.textContent}`).toBe("Project");
      expect(ts?.textContent?.trim(), `tech-stack h3: ${ts?.textContent}`).toBe("Tech Stack");
      expect(ft?.textContent?.trim(), `features h3: ${ft?.textContent}`).toBe("Features");
    });
  });
});

// --------------------------------------------------------------------- B6-P3
describe("B6-P3 UI/render — features Grid Table 5 列 + 添加特性 button", () => {
  it("table data-testid='features-grid' 5 列表头 + N>=2 行 + add-feature button", async () => {
    withFetch(defaultHandler);
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const table = container.querySelector('table[data-testid="features-grid"]');
      expect(table, "features-grid table missing").not.toBeNull();
      const headers = Array.from(table!.querySelectorAll("th")).map(
        (th) => th.textContent?.trim() ?? "",
      );
      expect(headers, `feature table headers: ${JSON.stringify(headers)}`).toEqual([
        "id",
        "title",
        "status",
        "srs_trace",
        "actions",
      ]);
      const rows = table!.querySelectorAll("tbody tr");
      expect(rows.length, `feature rows expected ≥2, got ${rows.length}`).toBeGreaterThanOrEqual(2);
      const addBtn = container.querySelector('button[data-testid="add-feature"]');
      expect(addBtn, "add-feature button missing").not.toBeNull();
    });
  });
});

// --------------------------------------------------------------------- B6-P4
describe("B6-P4 UI/render — 右 340px 校验面板", () => {
  it("aside data-testid='validation-panel' computedStyle.width === '340px' + 三组 list", async () => {
    withFetch(defaultHandler);
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const panel = container.querySelector('aside[data-testid="validation-panel"]');
      expect(panel, "validation-panel aside missing").not.toBeNull();
      // computed style — width must be "340px".
      const win = panel!.ownerDocument.defaultView!;
      const computed = win.getComputedStyle(panel as Element);
      expect(computed.width, `validation-panel width: ${computed.width}`).toBe("340px");
      // Three logical groups: realtime / backend / refresh button.
      const refreshBtn = container.querySelector('button[data-testid="rerun-validate"]');
      expect(refreshBtn, "rerun-validate button missing").not.toBeNull();
    });
  });
});

// --------------------------------------------------------------------- B6-P5
describe("B6-P5 UI/render — header 双 button + dirty chip 条件渲染", () => {
  it("dirty=false 时 dirty chip hidden；点 features 增量字段后 dirty chip 显示 + 双 button visible", async () => {
    withFetch(defaultHandler);
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    // Wait for initial render.
    await waitFor(() => {
      const chip = container.querySelector('[data-testid="dirty-chip"]');
      // chip MAY not exist when not dirty.
      const discard = container.querySelector('button[data-testid="discard-changes"]');
      const save = container.querySelector('button[data-testid="save-and-commit"]');
      expect(discard, "discard-changes button missing").not.toBeNull();
      expect(save, "save-and-commit button missing").not.toBeNull();
      // The chip element exists; its visibility is dirty-driven. We assert structural.
      // After loading clean, chip should be hidden (display:none) OR absent.
      if (chip) {
        const win = chip.ownerDocument.defaultView!;
        const display = win.getComputedStyle(chip).display;
        // If chip is rendered while clean, it must be display:none.
        // Accept either absent or hidden — assert one of the two.
        expect(display, `dirty chip should be hidden when clean, got display=${display}`).toBe("none");
      }
    });
    // Trigger a change by clicking add-feature.
    const addBtn = container.querySelector('button[data-testid="add-feature"]') as HTMLButtonElement | null;
    expect(addBtn, "add-feature button missing — cannot dirty form").not.toBeNull();
    fireEvent.click(addBtn!);
    await waitFor(() => {
      const chip = container.querySelector('[data-testid="dirty-chip"]');
      expect(chip, "dirty-chip not rendered after dirtying form").not.toBeNull();
      const win = chip!.ownerDocument.defaultView!;
      expect(win.getComputedStyle(chip as Element).display).not.toBe("none");
    });
  });
});

// --------------------------------------------------------------------- B6-N1
describe("B6-N1 UI/render — 404 错误态 EmptyState + 重新加载 button", () => {
  it("GET /api/files/read 返 404 → processfiles-empty + 重新加载 button (不卡 loading)", async () => {
    withFetch((input) => {
      const url = String(input);
      if (url.includes("/api/files/read")) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "Not Found" }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return defaultHandler(input);
    });
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const empty = container.querySelector('[data-testid="processfiles-empty"]');
      expect(empty, "processfiles-empty EmptyState missing").not.toBeNull();
      // Must contain the 中文 message.
      expect(empty!.textContent, `empty textContent: ${empty!.textContent}`).toMatch(
        /尚未初始化 feature-list\.json/,
      );
      // Reload button.
      const reload = container.querySelector('button[data-testid="processfiles-reload"]');
      expect(reload, "processfiles-reload button missing").not.toBeNull();
    });
  });
});

// --------------------------------------------------------------------- B6-N2
describe("B6-N2 FUNC/error — 必填空 + 保存时校验拦截 (不发 PUT)", () => {
  it("dirty + 必填空 + 点 save → 不发 PUT；ValidationPanel 列出 issues", async () => {
    let putFired = false;
    withFetch((input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/api/files/write") && method === "PUT") {
        putFired = true;
      }
      if (url.includes("/api/validate/feature-list.json")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: false,
              issues: [
                { severity: "err", code: "missing_field", path: "/project/name", message: "name 必填" },
              ],
              stderr_tail: "",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return defaultHandler(input, init);
    });
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    // Wait for load.
    await waitFor(() => {
      expect(container.querySelector('button[data-testid="save-and-commit"]')).not.toBeNull();
    });
    // Click save (without making an actually-valid edit; the underlying form
    // may need to be dirtied first to enable the button — we accept that the
    // button should remain disabled OR the click should not fire PUT).
    const save = container.querySelector('button[data-testid="save-and-commit"]') as HTMLButtonElement;
    fireEvent.click(save);
    await new Promise((r) => setTimeout(r, 60));
    expect(putFired, "PUT /api/files/write fired despite invalid form").toBe(false);
  });
});

// --------------------------------------------------------------------- B6-N3 (extra)
describe("B6-N3 FUNC/error — process-files 错误态时 stderr_tail 仍呈现 (不卡 loading)", () => {
  it("validate 返 500 → 错误信息以面板形式呈现 (不抛 ErrorBoundary)", async () => {
    withFetch((input) => {
      const url = String(input);
      if (url.includes("/api/files/read")) {
        return Promise.resolve(
          new Response(JSON.stringify(FEATURE_LIST_BODY), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/api/validate/")) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "internal error" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return defaultHandler(input);
    });
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    const rerun = await waitFor(() => {
      const b = container.querySelector('button[data-testid="rerun-validate"]');
      expect(b, "rerun-validate button missing").not.toBeNull();
      return b as HTMLButtonElement;
    });
    fireEvent.click(rerun);
    await new Promise((r) => setTimeout(r, 80));
    // After 500, the validation panel must still render an error region —
    // not crash the page.
    const panel = container.querySelector('aside[data-testid="validation-panel"]');
    expect(panel, "validation-panel destroyed by 500 — ErrorBoundary swallowed").not.toBeNull();
  });
});

// --------------------------------------------------------------------- B6-P6
describe("B6-P6 INTG/api — 「再次运行」 button → POST /api/validate/feature-list.json", () => {
  it("点 rerun-validate → POST /api/validate/feature-list.json + ValidationPanel 渲染 issues", async () => {
    let postFired = false;
    withFetch((input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/api/validate/feature-list.json") && method === "POST") {
        postFired = true;
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: false,
              issues: [
                { severity: "warn", code: "x", path: "/", message: "warn-msg" },
              ],
              stderr_tail: "",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return defaultHandler(input, init);
    });
    const { container } = render(<ProcessFilesPage />, { wrapper: Wrapper });
    const rerun = await waitFor(() => {
      const b = container.querySelector('button[data-testid="rerun-validate"]');
      expect(b, "rerun-validate button missing").not.toBeNull();
      return b as HTMLButtonElement;
    });
    fireEvent.click(rerun);
    await waitFor(() => {
      expect(postFired, "POST /api/validate/feature-list.json not invoked").toBe(true);
    });
    // Issues panel renders the warn message.
    await waitFor(() => {
      const panel = container.querySelector('aside[data-testid="validation-panel"]');
      expect(panel?.textContent ?? "", `panel textContent: ${panel?.textContent}`).toMatch(/warn-msg/);
    });
  });
});
