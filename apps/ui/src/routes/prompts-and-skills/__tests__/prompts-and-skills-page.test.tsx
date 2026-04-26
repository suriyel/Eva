/**
 * PromptsAndSkillsPage —— /skills SkillTreeViewer + classifier prompt 编辑历史 +
 *                         SkillsInstall + 路径穿越拦截
 *
 * Traces To 特性 22 design §Test Inventory 22-06 / 22-07 / 22-08 / 22-27 /
 *                   22-37 / 22-41 / 22-42 ·
 *           §Interface Contract B (useSkillTree / usePromptHistory /
 *                   useUpdateClassifierPrompt / useSkillsInstall / SkillTreeViewer) ·
 *           §Visual Rendering Contract skill-tree-viewer / prompt-editor /
 *                   prompt-history ·
 *           SRS FR-033 + IFR-006.
 *
 * Red 阶段：`apps/ui/src/routes/prompts-and-skills/index.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「树未递归」→ 22-06 readonly 节点数 < 6 FAIL
 *   - 「PUT 后 history 不刷新」→ 22-07 li 数量未 +1 FAIL
 *   - 「`..` 未拦截 / 错误吞掉」→ 22-08 toast 缺失 FAIL
 *   - 「URL 白名单失效」→ 22-37 file:// 接受 FAIL
 *   - 「entries=[] 时 crash」→ 22-41 EmptyState 缺失 FAIL
 *
 * [unit] —— uses fetch mocks; integration via tests/integration/test_f22_real_*.py.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PromptsAndSkillsPage } from "@/routes/prompts-and-skills";
import { SkillTreeViewer } from "@/routes/prompts-and-skills/components/skill-tree-viewer";

const originalFetch = globalThis.fetch;

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/skills"]}>{children}</MemoryRouter>
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

const TREE_3PLUGINS_2SKILLS = {
  name: "root",
  path: "",
  kind: "plugin" as const,
  children: [
    {
      name: "longtaskforagent",
      path: "longtaskforagent",
      kind: "plugin" as const,
      children: [
        { name: "design", path: "longtaskforagent/skills/design", kind: "skill" as const, children: [] },
        { name: "tdd", path: "longtaskforagent/skills/tdd", kind: "skill" as const, children: [] },
      ],
    },
    {
      name: "claude-flow",
      path: "claude-flow",
      kind: "plugin" as const,
      children: [
        { name: "review", path: "claude-flow/skills/review", kind: "skill" as const, children: [] },
        { name: "test", path: "claude-flow/skills/test", kind: "skill" as const, children: [] },
      ],
    },
    {
      name: "context7",
      path: "context7",
      kind: "plugin" as const,
      children: [
        { name: "docs", path: "context7/skills/docs", kind: "skill" as const, children: [] },
        { name: "search", path: "context7/skills/search", kind: "skill" as const, children: [] },
      ],
    },
  ],
};

function fetchByPath(handlers: Record<string, (init?: RequestInit) => Response>): ReturnType<typeof vi.fn> {
  return vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    for (const [pat, h] of Object.entries(handlers)) {
      if (url.includes(pat)) return h(init);
    }
    return jsonResp({ detail: "no handler" }, 404);
  });
}

// ---------------------------------------------------------------------------
// 22-06 FUNC/happy — SkillTree 3 plugin × 2 skill → ≥6 readonly nodes
// Traces To FR-033 AC1 + §IC useSkillTree + §VRC SkillTreeViewer
// ---------------------------------------------------------------------------
describe("22-06 FUNC/happy SkillTreeViewer 渲染 ≥6 readonly 节点", () => {
  it("/api/skills/tree 返回 3 plugin × 2 skill → readonly 节点数 ≥6", async () => {
    globalThis.fetch = fetchByPath({
      "/api/skills/tree": () => jsonResp(TREE_3PLUGINS_2SKILLS),
      "/api/prompts/classifier": () => jsonResp({ current: { content: "", hash: "h0" }, history: [] }),
    });
    const { container } = render(<PromptsAndSkillsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const nodes = container.querySelectorAll(
        '[data-component="skill-tree-viewer"] [data-skill-readonly="true"]',
      );
      expect(nodes.length).toBeGreaterThanOrEqual(6);
    });
  });

  it("SkillTreeViewer 直接渲染：onSelect 在点击 skill 节点时触发", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <SkillTreeViewer tree={TREE_3PLUGINS_2SKILLS} onSelect={onSelect} />,
    );
    const skillNode = container.querySelector(
      '[data-skill-readonly="true"][data-skill-path="longtaskforagent/skills/design"]',
    );
    expect(skillNode).not.toBeNull();
    fireEvent.click(skillNode as Element);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("longtaskforagent/skills/design");
  });

  it("SkillTreeViewer 节点带 aria-expanded 属性反映展开状态", () => {
    const { container } = render(
      <SkillTreeViewer tree={TREE_3PLUGINS_2SKILLS} onSelect={() => undefined} />,
    );
    const expanded = container.querySelectorAll('[aria-expanded]');
    expect(expanded.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// 22-07 FUNC/happy — useUpdateClassifierPrompt → history.length +1, hash diff
// Traces To FR-033 AC2 + §IC useUpdateClassifierPrompt + §VRC prompt-history
// ---------------------------------------------------------------------------
describe("22-07 FUNC/happy 编辑 classifier prompt → 历史追加", () => {
  it("PUT /api/prompts/classifier → history.length 由 2 → 3，新 hash 与旧 history[0] 不同", async () => {
    const initial = {
      current: { content: "old prompt", hash: "h0" },
      history: [
        { hash: "hA", content_summary: "v0", created_at: "2026-04-25T00:00:00Z" },
        { hash: "hB", content_summary: "v1", created_at: "2026-04-26T00:00:00Z" },
      ],
    };
    const after = {
      current: { content: "new prompt v2", hash: "h2" },
      history: [
        { hash: "h2", content_summary: "v2", created_at: "2026-04-26T01:00:00Z" },
        { hash: "hA", content_summary: "v0", created_at: "2026-04-25T00:00:00Z" },
        { hash: "hB", content_summary: "v1", created_at: "2026-04-26T00:00:00Z" },
      ],
    };
    let callCount = 0;
    globalThis.fetch = fetchByPath({
      "/api/skills/tree": () => jsonResp(TREE_3PLUGINS_2SKILLS),
      "/api/prompts/classifier": (init) => {
        callCount += 1;
        if (init?.method === "PUT") return jsonResp(after);
        return jsonResp(callCount > 1 ? after : initial);
      },
    });
    const { container } = render(<PromptsAndSkillsPage />, { wrapper: Wrapper });
    // 等历史列表初始 2 条出现
    await waitFor(() => {
      const items = container.querySelectorAll('[data-component="prompt-history"] li');
      expect(items.length).toBe(2);
    });
    // 进入编辑模式
    fireEvent.click(container.querySelector('[data-testid="prompt-edit-btn"]') as Element);
    const editor = container.querySelector('[data-testid="prompt-editor-textarea"]') as HTMLTextAreaElement;
    fireEvent.change(editor, { target: { value: "new prompt v2" } });
    fireEvent.click(container.querySelector('[data-testid="prompt-save-btn"]') as Element);
    await waitFor(() => {
      const items = container.querySelectorAll('[data-component="prompt-history"] li');
      expect(items.length).toBe(3);
    });
    const items = Array.from(
      container.querySelectorAll<HTMLElement>('[data-component="prompt-history"] li'),
    );
    expect(items[0].getAttribute("data-hash")).toBe("h2");
    expect(items[0].getAttribute("data-hash")).not.toBe("hA");
  });
});

// ---------------------------------------------------------------------------
// 22-08 SEC/path-traversal — useFileTree('docs/../etc') → 400 toast
// Traces To FR-033 SEC + §IC useFileTree Raises 400
// ---------------------------------------------------------------------------
describe("22-08 SEC/path-traversal 后端 400 toast", () => {
  it("useSkillTree 拒绝含 '..' 的 path → hook error.status===400 + toast 显示", async () => {
    globalThis.fetch = fetchByPath({
      "/api/skills/tree": () =>
        jsonResp({ detail: { code: "path_traversal", message: ".. forbidden" } }, 400),
      "/api/prompts/classifier": () => jsonResp({ current: { content: "", hash: "" }, history: [] }),
    });
    const { container } = render(<PromptsAndSkillsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const toast = container.querySelector('[data-testid="skill-tree-error-toast"]');
      expect(toast).not.toBeNull();
      expect(toast?.textContent ?? "").toMatch(/path_traversal|\.\./);
    });
    // 没有任何 readonly 节点被渲染
    expect(
      container.querySelectorAll(
        '[data-component="skill-tree-viewer"] [data-skill-readonly="true"]',
      ).length,
    ).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 22-27 UI/render — SkillTreeViewer readonly 节点正向渲染（vitest 等价 [devtools]）
// Traces To §VRC SkillTreeViewer readonly + devtools（[devtools] 真浏览器延 ST）
// ---------------------------------------------------------------------------
describe("22-27 UI/render SkillTreeViewer readonly 节点 + 锁图标", () => {
  it("/skills 加载后 [data-skill-readonly='true'] 节点存在 + 至少 1 个 lucide-lock svg 子节点", async () => {
    globalThis.fetch = fetchByPath({
      "/api/skills/tree": () => jsonResp(TREE_3PLUGINS_2SKILLS),
      "/api/prompts/classifier": () => jsonResp({ current: { content: "", hash: "" }, history: [] }),
    });
    const { container } = render(<PromptsAndSkillsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const readonly = container.querySelectorAll(
        '[data-component="skill-tree-viewer"] [data-skill-readonly="true"]',
      );
      expect(readonly.length).toBeGreaterThanOrEqual(1);
    });
    const firstReadonly = container.querySelector(
      '[data-component="skill-tree-viewer"] [data-skill-readonly="true"]',
    );
    // 锁图标存在（lucide 渲染为 svg）
    expect(firstReadonly?.querySelector("svg")).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 22-37 SEC/url-whitelist — useSkillsInstall file:// → 400
// Traces To INT-009 + §IC useSkillsInstall Raises 400
// ---------------------------------------------------------------------------
describe("22-37 SEC/url-whitelist file:// 拒绝", () => {
  it("提交 file:///etc/passwd → POST /api/skills/install 返 400 → toast 拒绝", async () => {
    globalThis.fetch = fetchByPath({
      "/api/skills/tree": () => jsonResp(TREE_3PLUGINS_2SKILLS),
      "/api/prompts/classifier": () => jsonResp({ current: { content: "", hash: "" }, history: [] }),
      "/api/skills/install": () =>
        jsonResp({ detail: { code: "url_not_whitelisted", message: "file:// scheme rejected" } }, 400),
    });
    const { container } = render(<PromptsAndSkillsPage />, { wrapper: Wrapper });
    await waitFor(() =>
      expect(container.querySelector('[data-component="skill-tree-viewer"]')).not.toBeNull(),
    );
    // 打开安装 modal
    fireEvent.click(container.querySelector('[data-testid="skills-install-open-btn"]') as Element);
    const urlInput = await waitFor(() => {
      const i = container.querySelector('[data-testid="skills-install-url-input"]');
      expect(i).not.toBeNull();
      return i as HTMLInputElement;
    });
    fireEvent.change(urlInput, { target: { value: "file:///etc/passwd" } });
    fireEvent.click(container.querySelector('[data-testid="skills-install-submit-btn"]') as Element);
    await waitFor(() => {
      const toast = container.querySelector('[data-testid="skills-install-error-toast"]');
      expect(toast).not.toBeNull();
      expect(toast?.textContent ?? "").toMatch(/url_not_whitelisted|file:\/\/|rejected/);
    });
  });
});

// ---------------------------------------------------------------------------
// 22-41 BNDRY/empty-tree — entries=[] → EmptyState
// Traces To §BC useSkillTree + §VRC SkillTreeViewer
// ---------------------------------------------------------------------------
describe("22-41 BNDRY/empty-tree 空树 EmptyState", () => {
  it("/api/skills/tree 返回 children=[] → EmptyState 渲染 + 无 crash", async () => {
    globalThis.fetch = fetchByPath({
      "/api/skills/tree": () =>
        jsonResp({ name: "root", path: "", kind: "plugin", children: [] }),
      "/api/prompts/classifier": () => jsonResp({ current: { content: "", hash: "" }, history: [] }),
    });
    const { container } = render(<PromptsAndSkillsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const empty = container.querySelector('[data-testid="skill-tree-empty-state"]');
      expect(empty).not.toBeNull();
      expect(empty?.textContent ?? "").toMatch(/暂无.*skill|empty/i);
    });
    expect(
      container.querySelectorAll(
        '[data-component="skill-tree-viewer"] [data-skill-readonly="true"]',
      ).length,
    ).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 22-42 BNDRY/long-prompt — content length 1MB+1 → 400
// Traces To §BC useUpdateClassifierPrompt content 长度
// ---------------------------------------------------------------------------
describe("22-42 BNDRY/long-prompt 大 payload 拒绝", () => {
  it("提交 1MB+1 字符 → 后端 400 → toast 显示 + history 不变", async () => {
    const HUGE = "x".repeat(1024 * 1024 + 1);
    const initial = {
      current: { content: "p", hash: "h0" },
      history: [{ hash: "hA", content_summary: "v0", created_at: "2026-04-25T00:00:00Z" }],
    };
    globalThis.fetch = fetchByPath({
      "/api/skills/tree": () => jsonResp(TREE_3PLUGINS_2SKILLS),
      "/api/prompts/classifier": (init) => {
        if (init?.method === "PUT") {
          return jsonResp({ detail: { code: "payload_too_large", message: "content >1MB" } }, 400);
        }
        return jsonResp(initial);
      },
    });
    const { container } = render(<PromptsAndSkillsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const items = container.querySelectorAll('[data-component="prompt-history"] li');
      expect(items.length).toBe(1);
    });
    fireEvent.click(container.querySelector('[data-testid="prompt-edit-btn"]') as Element);
    const editor = container.querySelector('[data-testid="prompt-editor-textarea"]') as HTMLTextAreaElement;
    fireEvent.change(editor, { target: { value: HUGE } });
    fireEvent.click(container.querySelector('[data-testid="prompt-save-btn"]') as Element);
    await waitFor(() => {
      const toast = container.querySelector('[data-testid="prompt-save-error-toast"]');
      expect(toast).not.toBeNull();
      expect(toast?.textContent ?? "").toMatch(/payload_too_large|>1MB/);
    });
    // history 不变
    const items = container.querySelectorAll('[data-component="prompt-history"] li');
    expect(items.length).toBe(1);
  });
});
