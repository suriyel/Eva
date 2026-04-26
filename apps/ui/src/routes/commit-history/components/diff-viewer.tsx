/**
 * DiffViewer — F22 §IC Section E.
 *
 * Renders the parsed ``DiffPayload`` files; binary files render via
 * ``BinaryDiffPlaceholder``, text files render lines with ``data-line-type``
 * attributes (add/del/context). Background colours are CSS variables so
 * design tokens (``--diff-add-bg`` / ``--diff-del-bg``) drive theming.
 */
import * as React from "react";
import type { DiffPayload } from "../../../lib/zod-schemas";
import { BinaryDiffPlaceholder } from "./binary-diff-placeholder";

export interface DiffViewerProps {
  diff: DiffPayload;
}

export function DiffViewer(props: DiffViewerProps): React.ReactElement {
  const { diff } = props;
  const files = diff?.files ?? [];
  return (
    <div data-component="diff-viewer">
      {files.length === 0 && (
        <div data-testid="diff-empty-state">暂无 diff 数据</div>
      )}
      {files.map((file) => {
        if (file.kind === "binary") {
          return (
            <BinaryDiffPlaceholder
              key={file.path}
              file={{ path: file.path, kind: "binary" }}
            />
          );
        }
        const hunks = file.hunks ?? [];
        return (
          <div key={file.path} data-diff-file={file.path}>
            <div data-component="diff-file-header">{file.path}</div>
            {hunks.map((hunk, hi) => (
              <div key={hi} data-component="diff-hunk">
                {hunk.header && (
                  <div className="diff-hunk-header">{hunk.header}</div>
                )}
                {(hunk.lines ?? []).map((line, li) => (
                  <div
                    key={li}
                    className="diff-line"
                    data-line-type={line.type}
                    style={{
                      background:
                        line.type === "add"
                          ? "var(--diff-add-bg, rgba(46,160,67,0.15))"
                          : line.type === "del"
                          ? "var(--diff-del-bg, rgba(248,81,73,0.15))"
                          : "transparent",
                    }}
                  >
                    {line.content}
                  </div>
                ))}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
