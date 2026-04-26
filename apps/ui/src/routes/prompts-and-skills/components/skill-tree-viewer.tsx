/**
 * SkillTreeViewer — F22 §IC Section B.
 * Recursive readonly tree with lock icon (F12 Icons re-use); onSelect fires
 * on leaf click; aria-expanded reflects expansion state.
 */
import * as React from "react";
import type { SkillTreeNode } from "../../../lib/zod-schemas";

export interface SkillTreeViewerProps {
  tree: SkillTreeNode;
  onSelect: (path: string) => void;
}

function LockIcon(): React.ReactElement {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      data-icon="lock"
    >
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function TreeNode({
  node,
  onSelect,
}: {
  node: SkillTreeNode;
  onSelect: (path: string) => void;
}): React.ReactElement {
  const [expanded, setExpanded] = React.useState<boolean>(true);
  const hasChildren = Array.isArray(node.children) && node.children.length > 0;
  return (
    <li
      data-skill-readonly="true"
      data-skill-path={node.path}
      data-skill-kind={node.kind}
      aria-expanded={hasChildren ? (expanded ? "true" : "false") : undefined}
      onClick={(e) => {
        e.stopPropagation();
        if (hasChildren) {
          setExpanded((v) => !v);
        } else {
          onSelect(node.path);
        }
      }}
      style={{ cursor: "pointer", listStyle: "none", paddingLeft: 12 }}
    >
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        <LockIcon />
        <span>{node.name}</span>
      </span>
      {hasChildren && expanded && (
        <ul style={{ listStyle: "none", paddingLeft: 12, margin: 0 }}>
          {node.children!.map((child) => (
            <TreeNode key={child.path || child.name} node={child} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function SkillTreeViewer(props: SkillTreeViewerProps): React.ReactElement {
  const { tree, onSelect } = props;
  const isEmpty =
    !tree || (!Array.isArray(tree.children) || tree.children.length === 0);

  return (
    <div data-component="skill-tree-viewer">
      {isEmpty ? (
        <div data-testid="skill-tree-empty-state">暂无 skill 可显示 (empty)</div>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {tree.children!.map((child) => (
            <TreeNode key={child.path || child.name} node={child} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </div>
  );
}
