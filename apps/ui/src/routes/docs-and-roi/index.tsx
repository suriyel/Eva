/**
 * DocsAndROIPage — F22 §IC Section C · /docs (UCD §4.6).
 *
 * Three-pane layout: file tree (left) · markdown preview (center) ·
 * TOC (right) + RoiDisabledButton (top-right, v1.1 placeholder).
 */
import * as React from "react";
import { useFileTree, useFileContent } from "../../api/routes/files";
import { HttpError } from "../../api/client";
import { MarkdownPreview } from "./components/markdown-preview";
import { TocPanel } from "./components/toc-panel";
import { RoiDisabledButton } from "./components/roi-disabled-button";

const DEFAULT_ROOT = "docs/plans";

export function DocsAndROIPage(): React.ReactElement {
  const [root] = React.useState<string>(DEFAULT_ROOT);
  const [selected, setSelected] = React.useState<string | null>(null);

  const treeQ = useFileTree(root);
  const contentQ = useFileContent(selected);

  const entries = treeQ.data?.entries ?? [];
  const content = contentQ.data?.content ?? "";
  const truncated = contentQ.data?.truncated === true;
  const readErr = contentQ.error;

  return (
    <div data-component="docs-and-roi-page" style={{ display: "flex", gap: 16 }}>
      {treeQ.data ? (
        <div data-component="docs-tree" style={{ flex: 1, minWidth: 200 }}>
          <h4>{root}</h4>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {entries.map((e) => (
              <li
                key={e.path}
                data-file-path={e.path}
                data-file-kind={e.kind}
                onClick={() => setSelected(e.path)}
                style={{
                  cursor: "pointer",
                  padding: "2px 4px",
                  background: selected === e.path ? "var(--bg-elev, #2a2f3a)" : undefined,
                }}
              >
                {e.path.split("/").pop()}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div style={{ flex: 1, minWidth: 200 }}>
          {treeQ.isLoading ? "加载中…" : null}
        </div>
      )}
      <div style={{ flex: 2 }}>
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <RoiDisabledButton />
        </div>
        {truncated && (
          <div data-testid="docs-truncated-banner" role="status">
            已截断（truncated）— 文件内容超过预设阈值
          </div>
        )}
        {readErr ? (
          <div data-testid="docs-read-error-toast" role="alert">
            {readErr instanceof HttpError
              ? `${readErr.status}: ${describePathError(readErr.detail)}`
              : String(readErr.message)}
            <MarkdownPreview content="" />
          </div>
        ) : (
          <MarkdownPreview content={content} />
        )}
      </div>
      <div style={{ flex: 1, minWidth: 160 }}>
        <TocPanel content={content} />
      </div>
    </div>
  );
}

function describePathError(detail: unknown): string {
  if (detail && typeof detail === "object" && "detail" in (detail as Record<string, unknown>)) {
    const inner = (detail as { detail: unknown }).detail;
    if (inner && typeof inner === "object") {
      const obj = inner as { code?: string; message?: string };
      const parts = [obj.code, obj.message].filter(Boolean);
      if (parts.length > 0) return parts.join(": ");
    }
  }
  return "";
}
