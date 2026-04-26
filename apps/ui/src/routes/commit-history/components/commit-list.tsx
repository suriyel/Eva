/**
 * CommitList — F22 §IC Section E.
 * Each row carries ``data-sha={sha}``; selected row gets ``data-selected="true"``.
 */
import * as React from "react";
import type { GitCommit } from "../../../lib/zod-schemas";

export interface CommitListProps {
  commits: GitCommit[];
  selected: string | null;
  onSelect: (sha: string) => void;
}

export function CommitList(props: CommitListProps): React.ReactElement {
  const { commits, selected, onSelect } = props;
  if (!commits || commits.length === 0) {
    return (
      <div data-component="commit-list">
        <div data-testid="commit-list-empty-state">暂无 commits</div>
      </div>
    );
  }
  return (
    <ul data-component="commit-list" style={{ listStyle: "none", padding: 0 }}>
      {commits.map((c) => (
        <li
          key={c.sha}
          data-sha={c.sha}
          data-selected={selected === c.sha ? "true" : undefined}
          onClick={() => onSelect(c.sha)}
          style={{
            cursor: "pointer",
            padding: 4,
            background:
              selected === c.sha ? "var(--bg-elev, #2a2f3a)" : "transparent",
          }}
        >
          <span>{c.sha.slice(0, 7)}</span>{" "}
          <span>{c.subject}</span>
        </li>
      ))}
    </ul>
  );
}
