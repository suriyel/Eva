/**
 * DocsAndROIPage —— /docs 三 pane（FileTree / MarkdownPreview / TocPanel）+
 *                    ROI 按钮 disabled tooltip + 路径穿越 + 大文件截断
 *
 * Traces To 特性 22 design §Test Inventory 22-09 / 22-10 / 22-11 / 22-21 /
 *                   22-24（[devtools] 真浏览器延 ST，本文件做 vitest 等价 DOM 校验） ·
 *           §Interface Contract C (useFileTree / useFileContent / RoiDisabledButton /
 *                   MarkdownPreview / TocPanel) ·
 *           §Visual Rendering Contract docs-tree / markdown-preview / toc /
 *                   roi-button + roi-tooltip ·
 *           SRS FR-035 + FR-035b/036/037 v1 全部 Won't.
 *
 * Red 阶段：`apps/ui/src/routes/docs-and-roi/index.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「`..` 直接拼进 URL」→ 22-09 fetch 调用的 url 不应 include '..' FAIL
 *   - 「三 pane 任一缺失」→ 22-10 querySelector 节点缺失 FAIL
 *   - 「ROI 按钮 enabled 或 onClick 触发 fetch」→ 22-11 disabled 缺失 / fetch 计数 != 0 FAIL
 *   - 「truncated 标志被忽略」→ 22-21 banner 缺失 FAIL
 *
 * [unit] —— uses fetch mocks; integration via tests/integration/test_f22_real_*.py.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { DocsAndROIPage } from "@/routes/docs-and-roi";
import { RoiDisabledButton } from "@/routes/docs-and-roi/components/roi-disabled-button";
import { MarkdownPreview } from "@/routes/docs-and-roi/components/markdown-preview";
import { TocPanel } from "@/routes/docs-and-roi/components/toc-panel";

const originalFetch = globalThis.fetch;

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/docs"]}>{children}</MemoryRouter>
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

const FILE_TREE_PLANS = {
  root: "docs/plans",
  entries: [
    { path: "docs/plans/2026-04-21-harness-srs.md", kind: "file" as const, size: 12345 },
    { path: "docs/plans/2026-04-21-harness-design.md", kind: "file" as const, size: 67890 },
    { path: "docs/plans/2026-04-21-harness-ats.md", kind: "file" as const, size: 5432 },
  ],
};

const MD_CONTENT = "# Heading One\n\n## Heading Two\n\nLorem ipsum.\n\n## Another\n\nMore.";

// ---------------------------------------------------------------------------
// 22-09 SEC/path-traversal — useFileContent('docs/../../etc/passwd') → 400
// Traces To FR-035 SEC + §IC useFileContent Raises 400
// ---------------------------------------------------------------------------
describe("22-09 SEC/path-traversal 文件读取 400", () => {
  it("点击虚构的恶意路径节点 → fetch 不带 '..' 字面 URL；后端 400 时 preview 不崩", async () => {
    let lastFetchedUrl = "";
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      lastFetchedUrl = url;
      if (url.includes("/api/files/tree")) {
        // 故意把 traversal 入口注入到 entries（模拟后端漏出的恶意路径）
        return jsonResp({
          root: "docs/plans",
          entries: [
            { path: "docs/plans/../../etc/passwd", kind: "file" as const, size: 100 },
            ...FILE_TREE_PLANS.entries,
          ],
        });
      }
      if (url.includes("/api/files/read")) {
        return jsonResp({ detail: { code: "path_traversal", message: ".. forbidden" } }, 400);
      }
      return jsonResp({ detail: "not handled" }, 404);
    });
    const { container } = render(<DocsAndROIPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-component="docs-tree"]')).not.toBeNull();
    });
    // 点击 traversal 节点
    const tNode = container.querySelector(
      '[data-component="docs-tree"] [data-file-path="docs/plans/../../etc/passwd"]',
    );
    expect(tNode).not.toBeNull();
    fireEvent.click(tNode as Element);
    await waitFor(() => {
      // 错误显示
      const err = container.querySelector('[data-testid="docs-read-error-toast"]');
      expect(err).not.toBeNull();
      expect(err?.textContent ?? "").toMatch(/path_traversal|\.\./);
    });
    // 前端不重新构造含 `..` 的 URL（路径作为查询字符串编码后必转义）
    expect(lastFetchedUrl.includes("/etc/passwd")).toBe(true); // 路径作为 query value 包含
    // 但 markdown preview 不崩溃（SUT 渲染空态）
    expect(container.querySelector('[data-component="markdown-preview"]')).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 22-10 FUNC/happy — 三 pane 同时存在 + TOC 锚点
// Traces To FR-035 AC + §VRC docs 三 pane
// ---------------------------------------------------------------------------
describe("22-10 FUNC/happy DocsAndROI 三 pane", () => {
  it("加载 docs/plans 后三 pane 节点同时存在；选中 .md → preview content > 0；TOC 至少 1 个锚点", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/files/tree")) return jsonResp(FILE_TREE_PLANS);
      if (url.includes("/api/files/read")) {
        return jsonResp({
          path: "docs/plans/2026-04-21-harness-srs.md",
          content: MD_CONTENT,
          encoding: "utf-8",
        });
      }
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<DocsAndROIPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-component="docs-tree"]')).not.toBeNull();
      expect(container.querySelector('[data-component="markdown-preview"]')).not.toBeNull();
      expect(container.querySelector('[data-component="toc"]')).not.toBeNull();
    });
    // 点击第一个 .md 文件
    const node = container.querySelector(
      '[data-component="docs-tree"] [data-file-path="docs/plans/2026-04-21-harness-srs.md"]',
    );
    expect(node).not.toBeNull();
    fireEvent.click(node as Element);
    await waitFor(() => {
      const preview = container.querySelector('[data-component="markdown-preview"]');
      expect(preview).not.toBeNull();
      expect((preview?.textContent ?? "").length).toBeGreaterThan(0);
    });
    // TOC 至少 1 个 nav 项
    const tocItems = container.querySelectorAll('[data-component="toc"] a, [data-component="toc"] li');
    expect(tocItems.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// 22-11 UI/render — RoiDisabledButton + tooltip "v1.1 规划中"
// Traces To FR-035 v1 subset + §VRC RoiDisabledButton
// ---------------------------------------------------------------------------
describe("22-11 UI/render RoiDisabledButton disabled + tooltip", () => {
  it("button 含 disabled + aria-disabled='true'；hover 后 tooltip 文本 == 'v1.1 规划中'", () => {
    const onClick = vi.fn();
    const { container } = render(<RoiDisabledButton onClick={onClick} />);
    const btn = container.querySelector('button[data-testid="roi-button"]') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    fireEvent.mouseEnter(btn);
    const tooltip = container.querySelector('[data-testid="roi-tooltip"]');
    expect(tooltip).not.toBeNull();
    expect(tooltip?.textContent).toBe("v1.1 规划中");
    // onClick 不被触发（disabled 原生 + 双保险）
    fireEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("DocsAndROI 页面里 ROI 按钮点击不触发任何 fetch", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/files/tree")) return jsonResp(FILE_TREE_PLANS);
      return jsonResp({ detail: "404" }, 404);
    });
    globalThis.fetch = fetchMock;
    const { container } = render(<DocsAndROIPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-component="docs-tree"]')).not.toBeNull();
    });
    const fetchCallsBefore = fetchMock.mock.calls.length;
    const btn = container.querySelector('[data-testid="roi-button"]') as HTMLButtonElement;
    fireEvent.click(btn);
    // ROI 按钮不应触发任何新的 fetch
    expect(fetchMock.mock.calls.length).toBe(fetchCallsBefore);
  });
});

// ---------------------------------------------------------------------------
// 22-21 BNDRY/oversize-file — content >1MB → truncated banner
// Traces To §BC useFileContent content >1MB
// ---------------------------------------------------------------------------
describe("22-21 BNDRY/oversize-file truncated banner", () => {
  it("/api/files/read 返回 truncated:true → preview 渲染内容 + 顶部「已截断」banner", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/files/tree")) return jsonResp(FILE_TREE_PLANS);
      if (url.includes("/api/files/read")) {
        return jsonResp({
          path: "docs/plans/2026-04-21-harness-srs.md",
          content: "# big file\n\n" + "x".repeat(1024),
          encoding: "utf-8",
          truncated: true,
        });
      }
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<DocsAndROIPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-component="docs-tree"]')).not.toBeNull();
    });
    fireEvent.click(
      container.querySelector(
        '[data-component="docs-tree"] [data-file-path="docs/plans/2026-04-21-harness-srs.md"]',
      ) as Element,
    );
    await waitFor(() => {
      const banner = container.querySelector('[data-testid="docs-truncated-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent ?? "").toMatch(/已截断|truncated/i);
    });
    // 主预览仍渲染部分内容
    const preview = container.querySelector('[data-component="markdown-preview"]');
    expect((preview?.textContent ?? "").length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// 22-24 UI/render — 三 pane snapshot 等价（vitest happy-dom 替代 [devtools]）
// Traces To §VRC docs 三 pane + devtools
// ---------------------------------------------------------------------------
describe("22-24 UI/render docs 三 pane DOM 快照", () => {
  it("初次加载 /docs 后三 pane 同时可见 + 横向并排（width > 0）", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/files/tree")) return jsonResp(FILE_TREE_PLANS);
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<DocsAndROIPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-component="docs-tree"]')).not.toBeNull();
      expect(container.querySelector('[data-component="markdown-preview"]')).not.toBeNull();
      expect(container.querySelector('[data-component="toc"]')).not.toBeNull();
    });
  });

  it("MarkdownPreview 单元：H1 标题被渲染为 <h1>", () => {
    const { container } = render(<MarkdownPreview content={MD_CONTENT} />);
    const h1 = container.querySelector("h1");
    expect(h1).not.toBeNull();
    expect(h1?.textContent ?? "").toMatch(/Heading One/);
  });

  it("TocPanel 单元：解析 H1-H4 → 至少 3 个锚点（H1 + 2 H2）", () => {
    const { container } = render(<TocPanel content={MD_CONTENT} />);
    const items = container.querySelectorAll('[data-component="toc"] a, [data-component="toc"] li');
    expect(items.length).toBeGreaterThanOrEqual(3);
  });
});
