/**
 * CommitHistoryPage —— /commits CommitList + DiffViewer + BinaryDiffPlaceholder +
 *                       NotAGitRepoBanner（非 git 502）+ 短 sha 边界
 *
 * Traces To 特性 22 design §Test Inventory 22-16 / 22-17 / 22-18 / 22-19 /
 *                   22-20 / 22-22 / 22-26 / 22-35 ·
 *           §Interface Contract E (useCommits / useDiff / CommitList / DiffViewer /
 *                   BinaryDiffPlaceholder / NotAGitRepoBanner) ·
 *           §Visual Rendering Contract commit-list / diff-viewer /
 *                   binary-diff-placeholder / not-a-git-repo-banner ·
 *           SRS FR-041 + IFR-005.
 *
 * Red 阶段：`apps/ui/src/routes/commit-history/index.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「commit 行 data-sha 缺失」→ 22-16 选择器命中 0 FAIL
 *   - 「DiffViewer 不消费 hunks」→ 22-17 .diff-line 节点 0 FAIL
 *   - 「DiffViewer 把空 hunks 喂 react-diff-view → crash」→ 22-18 ErrorBoundary 触发 FAIL
 *   - 「502 触发 ErrorBoundary 整页白屏」→ 22-19 banner 缺失 FAIL
 *   - 「commits=[] 时 CommitList[0] crash」→ 22-20 EmptyState 缺失 FAIL
 *   - 「短 sha 7 字符被前端拒绝」→ 22-22 fetch 不发出 FAIL
 *
 * [unit] —— uses fetch mocks; integration via tests/integration/test_f22_real_*.py.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CommitHistoryPage } from "@/routes/commit-history";
import { CommitList } from "@/routes/commit-history/components/commit-list";
import { DiffViewer } from "@/routes/commit-history/components/diff-viewer";
import { BinaryDiffPlaceholder } from "@/routes/commit-history/components/binary-diff-placeholder";
import { NotAGitRepoBanner } from "@/routes/commit-history/components/not-a-git-repo-banner";

const originalFetch = globalThis.fetch;

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/commits"]}>{children}</MemoryRouter>
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

const COMMITS_8 = Array.from({ length: 8 }).map((_, i) => ({
  sha: `${i.toString(16).padStart(8, "0")}1234567890abcdef1234567890abcdef12345678`.slice(0, 40),
  parents: i === 0 ? [] : [`${(i - 1).toString(16).padStart(8, "0")}1234567890abcdef1234567890abcdef12345678`.slice(0, 40)],
  author: "tester <t@example.com>",
  ts: `2026-04-${(20 + i).toString().padStart(2, "0")}T00:00:00Z`,
  subject: `feat: commit ${i}`,
  run_id: "R1",
  feature_id: 22,
}));

const TEXT_DIFF = {
  sha: COMMITS_8[0].sha,
  files: [
    {
      path: "src/index.tsx",
      kind: "text" as const,
      hunks: [
        {
          old_start: 1,
          old_lines: 2,
          new_start: 1,
          new_lines: 3,
          lines: [
            { type: "context" as const, content: " unchanged" },
            { type: "del" as const, content: "-old" },
            { type: "add" as const, content: "+new" },
            { type: "add" as const, content: "+extra" },
          ],
        },
      ],
    },
  ],
};

const BINARY_DIFF = {
  sha: COMMITS_8[1].sha,
  files: [
    {
      path: "logo.png",
      kind: "binary" as const,
      placeholder: true,
    },
  ],
};

// ---------------------------------------------------------------------------
// 22-16 FUNC/happy — 8 commits → 8 [data-sha] 行
// Traces To FR-041 AC1 + §IC useCommits + §VRC CommitList
// ---------------------------------------------------------------------------
describe("22-16 FUNC/happy CommitList 8 行", () => {
  it("/api/git/commits?run_id=R1 返 8 条 → CommitList 渲染 8 行；每行带 data-sha", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/git/commits")) return jsonResp(COMMITS_8);
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<CommitHistoryPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const rows = container.querySelectorAll('[data-component="commit-list"] [data-sha]');
      expect(rows.length).toBe(8);
    });
    // 第一行 data-sha 必为 40 字符或 sha 字符串
    const first = container.querySelector(
      '[data-component="commit-list"] [data-sha]',
    ) as HTMLElement | null;
    expect(first?.getAttribute("data-sha")).toBe(COMMITS_8[0].sha);
  });

  it("CommitList 单元：onSelect 在点击行时触发 + 选中行 data-selected='true'", () => {
    const onSelect = vi.fn();
    const { container, rerender } = render(
      <CommitList commits={COMMITS_8} selected={null} onSelect={onSelect} />,
    );
    const targetRow = container.querySelector(`[data-sha="${COMMITS_8[2].sha}"]`) as Element;
    fireEvent.click(targetRow);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(COMMITS_8[2].sha);
    rerender(<CommitList commits={COMMITS_8} selected={COMMITS_8[2].sha} onSelect={onSelect} />);
    const selRow = container.querySelector(`[data-sha="${COMMITS_8[2].sha}"]`) as Element;
    expect(selRow.getAttribute("data-selected")).toBe("true");
  });
});

// ---------------------------------------------------------------------------
// 22-17 FUNC/happy — 选中 commit → DiffViewer .diff-line ≥3
// Traces To FR-041 AC2 + §IC useDiff + §VRC DiffViewer
// ---------------------------------------------------------------------------
describe("22-17 FUNC/happy DiffViewer add/del 行", () => {
  it("点击 commit → /api/git/diff/:sha 返回 3 hunks → .diff-line 节点 ≥3 + add 行 + del 行", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/git/commits")) return jsonResp(COMMITS_8);
      if (url.includes("/api/git/diff/")) return jsonResp(TEXT_DIFF);
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<CommitHistoryPage />, { wrapper: Wrapper });
    const firstRow = await waitFor(() => {
      const r = container.querySelector('[data-component="commit-list"] [data-sha]');
      expect(r).not.toBeNull();
      return r as Element;
    });
    fireEvent.click(firstRow);
    await waitFor(() => {
      const lines = container.querySelectorAll('[data-component="diff-viewer"] .diff-line[data-line-type]');
      expect(lines.length).toBeGreaterThanOrEqual(3);
    });
    const addLines = container.querySelectorAll(
      '[data-component="diff-viewer"] .diff-line[data-line-type="add"]',
    );
    const delLines = container.querySelectorAll(
      '[data-component="diff-viewer"] .diff-line[data-line-type="del"]',
    );
    expect(addLines.length).toBeGreaterThanOrEqual(1);
    expect(delLines.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// 22-18 BNDRY/binary-diff — kind=binary → BinaryDiffPlaceholder + 不崩
// Traces To FR-041 BNDRY + §IC <BinaryDiffPlaceholder>
// ---------------------------------------------------------------------------
describe("22-18 BNDRY/binary-diff 占位渲染不崩", () => {
  it("DiffPayload kind=binary → BinaryDiffPlaceholder 含路径 + DiffViewer 不抛", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/git/commits")) return jsonResp(COMMITS_8);
      if (url.includes("/api/git/diff/")) return jsonResp(BINARY_DIFF);
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<CommitHistoryPage />, { wrapper: Wrapper });
    const firstRow = await waitFor(() => {
      const r = container.querySelector('[data-component="commit-list"] [data-sha]');
      expect(r).not.toBeNull();
      return r as Element;
    });
    fireEvent.click(firstRow);
    await waitFor(() => {
      const ph = container.querySelector('[data-component="binary-diff-placeholder"]');
      expect(ph).not.toBeNull();
      expect(ph?.textContent ?? "").toContain("logo.png");
    });
    expect(container.querySelector('[data-component="error-boundary"]')).toBeNull();
  });

  it("BinaryDiffPlaceholder 单元：渲染 path + aria-label", () => {
    const { container } = render(
      <BinaryDiffPlaceholder file={{ path: "assets/icon.png", kind: "binary" }} />,
    );
    const ph = container.querySelector('[data-component="binary-diff-placeholder"]');
    expect(ph).not.toBeNull();
    expect(ph?.textContent ?? "").toContain("assets/icon.png");
    expect(ph?.getAttribute("aria-label") ?? "").toMatch(/二进制|binary/i);
  });
});

// ---------------------------------------------------------------------------
// 22-19 FUNC/error — 502 not_a_git_repo → NotAGitRepoBanner（非整页白屏）
// Traces To IFR-005 + §IC useCommits Raises 502 + §VRC NotAGitRepoBanner
// ---------------------------------------------------------------------------
describe("22-19 FUNC/error NotAGitRepoBanner 渲染", () => {
  it("/api/git/commits 返 502 + body code='not_a_git_repo' → banner role='alert' 渲染", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/git/commits")) {
        return jsonResp({ detail: { code: "not_a_git_repo", message: "non-git directory" } }, 502);
      }
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<CommitHistoryPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const banner = container.querySelector('[data-testid="not-a-git-repo-banner"][role="alert"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent ?? "").toMatch(/非 git|not.*git/i);
    });
    // 整页未崩溃：CommitList 容器仍然存在（即使空）
    expect(container.querySelector('[data-component="commit-list"]')).not.toBeNull();
    expect(container.querySelector('[data-component="error-boundary"]')).toBeNull();
  });

  it("NotAGitRepoBanner 单元：show=false 返回 null；show=true 渲染 alert", () => {
    const { container, rerender } = render(<NotAGitRepoBanner show={false} />);
    expect(container.querySelector('[data-testid="not-a-git-repo-banner"]')).toBeNull();
    rerender(<NotAGitRepoBanner show={true} />);
    const banner = container.querySelector('[data-testid="not-a-git-repo-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.getAttribute("role")).toBe("alert");
  });
});

// ---------------------------------------------------------------------------
// 22-20 BNDRY/empty-list — commits=[] → EmptyState；DiffViewer 初始空态
// Traces To FR-041 + §VRC CommitList
// ---------------------------------------------------------------------------
describe("22-20 BNDRY/empty-list 0 条 commits", () => {
  it("/api/git/commits 返 [] → CommitList EmptyState；DiffViewer 不假设 commits[0] 存在", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/git/commits")) return jsonResp([]);
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<CommitHistoryPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const empty = container.querySelector('[data-testid="commit-list-empty-state"]');
      expect(empty).not.toBeNull();
    });
    expect(
      container.querySelectorAll('[data-component="commit-list"] [data-sha]').length,
    ).toBe(0);
    expect(container.querySelector('[data-component="error-boundary"]')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 22-22 BNDRY/sha-format — 短 sha 7 字符 仍发请求
// Traces To §BC useDiff(sha) length=7 vs 40
// ---------------------------------------------------------------------------
describe("22-22 BNDRY/sha-format 短 sha 不被前端拒绝", () => {
  it("通过 ?sha=abc1234 选中 commit → fetch 调用 /api/git/diff/abc1234（不要求 40 字符）", async () => {
    const SHORT_SHA = "abc1234";
    const SHORT_DIFF = {
      ...TEXT_DIFF,
      sha: SHORT_SHA,
      files: [
        { ...TEXT_DIFF.files[0], path: "short.tsx" },
      ],
    };
    let diffUrlSeen = "";
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/git/commits")) {
        return jsonResp([{ ...COMMITS_8[0], sha: SHORT_SHA }]);
      }
      if (url.includes("/api/git/diff/")) {
        diffUrlSeen = url;
        return jsonResp(SHORT_DIFF);
      }
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<CommitHistoryPage />, { wrapper: Wrapper });
    const firstRow = await waitFor(() => {
      const r = container.querySelector('[data-component="commit-list"] [data-sha]');
      expect(r).not.toBeNull();
      return r as Element;
    });
    fireEvent.click(firstRow);
    await waitFor(() => {
      expect(diffUrlSeen).toContain("/api/git/diff/");
      expect(diffUrlSeen).toContain(SHORT_SHA);
    });
    // DiffViewer 仍正常渲染
    await waitFor(() => {
      const lines = container.querySelectorAll(
        '[data-component="diff-viewer"] .diff-line[data-line-type]',
      );
      expect(lines.length).toBeGreaterThanOrEqual(1);
    });
  });
});

// ---------------------------------------------------------------------------
// 22-26 UI/render — DiffViewer + diff-line + tokens 变量取色（[devtools] 等价）
// Traces To §VRC DiffViewer + devtools
// ---------------------------------------------------------------------------
describe("22-26 UI/render DiffViewer DOM 快照", () => {
  it("选中 commit 后 [data-component='diff-viewer'] [data-line-type] 节点 ≥1", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/git/commits")) return jsonResp(COMMITS_8);
      if (url.includes("/api/git/diff/")) return jsonResp(TEXT_DIFF);
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<CommitHistoryPage />, { wrapper: Wrapper });
    fireEvent.click(
      (await waitFor(() => {
        const r = container.querySelector('[data-component="commit-list"] [data-sha]');
        expect(r).not.toBeNull();
        return r;
      })) as Element,
    );
    await waitFor(() => {
      const lines = container.querySelectorAll(
        '[data-component="diff-viewer"] [data-line-type]',
      );
      expect(lines.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("DiffViewer 单元：渲染 binary file → BinaryDiffPlaceholder 而非 .diff-line", () => {
    const { container } = render(<DiffViewer diff={BINARY_DIFF} />);
    expect(container.querySelector('[data-component="binary-diff-placeholder"]')).not.toBeNull();
    expect(container.querySelectorAll('.diff-line').length).toBe(0);
  });

  it("DiffViewer 单元：渲染 text file → 含 add + del 行", () => {
    const { container } = render(<DiffViewer diff={TEXT_DIFF} />);
    const addLines = container.querySelectorAll('.diff-line[data-line-type="add"]');
    const delLines = container.querySelectorAll('.diff-line[data-line-type="del"]');
    expect(addLines.length).toBeGreaterThanOrEqual(1);
    expect(delLines.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// 22-35 INTG/api — text + binary 混合分流（response schema 真实消费）
// Traces To §IC useDiff + IAPI-002 + IFR-005
// ---------------------------------------------------------------------------
describe("22-35 INTG/api text+binary 文件分流", () => {
  it("DiffPayload.files 含 1 text + 1 binary → DiffViewer 各自渲染各自组件", async () => {
    const MIXED = {
      sha: COMMITS_8[0].sha,
      files: [TEXT_DIFF.files[0], BINARY_DIFF.files[0]],
    };
    globalThis.fetch = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/api/git/commits")) return jsonResp(COMMITS_8);
      if (url.includes("/api/git/diff/")) return jsonResp(MIXED);
      return jsonResp({ detail: "404" }, 404);
    });
    const { container } = render(<CommitHistoryPage />, { wrapper: Wrapper });
    fireEvent.click(
      (await waitFor(() => {
        const r = container.querySelector('[data-component="commit-list"] [data-sha]');
        expect(r).not.toBeNull();
        return r;
      })) as Element,
    );
    await waitFor(() => {
      // 同时存在 text diff line 与 binary placeholder
      expect(
        container.querySelectorAll(
          '[data-component="diff-viewer"] .diff-line[data-line-type]',
        ).length,
      ).toBeGreaterThanOrEqual(1);
      expect(container.querySelector('[data-component="binary-diff-placeholder"]')).not.toBeNull();
    });
  });
});
