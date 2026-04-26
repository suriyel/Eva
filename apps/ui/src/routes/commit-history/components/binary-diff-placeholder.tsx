/**
 * BinaryDiffPlaceholder — F22 §IC Section E.
 * Renders a placeholder for binary files so DiffViewer never feeds empty
 * hunks to react-diff-view (FR-041 BNDRY).
 */
import * as React from "react";

export interface BinaryDiffPlaceholderProps {
  file: { path: string; kind: "binary" };
}

export function BinaryDiffPlaceholder(
  props: BinaryDiffPlaceholderProps,
): React.ReactElement {
  return (
    <div
      data-component="binary-diff-placeholder"
      aria-label="二进制文件 diff 占位 (binary)"
    >
      二进制文件: {props.file.path}
    </div>
  );
}
