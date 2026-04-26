/**
 * CommitHistoryPage — F22 §IC Section E · /commits (UCD §4.8).
 *
 * Composition:
 *   - useCommits → CommitList (left)
 *   - useDiff(selectedSha) → DiffViewer (right)
 *   - useCommits 502 not_a_git_repo → NotAGitRepoBanner (top)
 */
import * as React from "react";
import { useCommits, useDiff } from "../../api/routes/git";
import { HttpError } from "../../api/client";
import { CommitList } from "./components/commit-list";
import { DiffViewer } from "./components/diff-viewer";
import { NotAGitRepoBanner } from "./components/not-a-git-repo-banner";
import type { DiffPayload } from "../../lib/zod-schemas";

const EMPTY_DIFF: DiffPayload = { sha: "", files: [] };

export function CommitHistoryPage(): React.ReactElement {
  const commitsQ = useCommits();
  const [selected, setSelected] = React.useState<string | null>(null);
  const diffQ = useDiff(selected);

  const commits = commitsQ.data ?? [];

  const showNotGit = (() => {
    const err = commitsQ.error;
    if (!(err instanceof HttpError)) return false;
    if (err.status !== 502) return false;
    if (err.code === "not_a_git_repo") return true;
    // Inspect detail body for code field as well.
    const detail = err.detail as { detail?: { code?: string } } | unknown;
    if (
      detail &&
      typeof detail === "object" &&
      "detail" in (detail as Record<string, unknown>)
    ) {
      const inner = (detail as { detail: unknown }).detail;
      if (
        inner &&
        typeof inner === "object" &&
        (inner as { code?: string }).code === "not_a_git_repo"
      ) {
        return true;
      }
    }
    return false;
  })();

  return (
    <div data-component="commit-history-page" style={{ display: "flex", gap: 16 }}>
      <div style={{ flex: 1, minWidth: 240 }}>
        <NotAGitRepoBanner show={showNotGit} />
        <CommitList commits={commits} selected={selected} onSelect={setSelected} />
      </div>
      <div style={{ flex: 2 }}>
        <DiffViewer diff={diffQ.data ?? EMPTY_DIFF} />
      </div>
    </div>
  );
}
