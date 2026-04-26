/**
 * CrossFieldErrorList — F22 §IC Section D.
 * Renders backend-validation issues inline (FR-039 AC2: 错误内联展示而非 toast).
 */
import * as React from "react";

export interface CrossFieldIssue {
  path: string;
  level: "error" | "warning";
  message: string;
}

export interface CrossFieldErrorListProps {
  issues: CrossFieldIssue[];
}

export function CrossFieldErrorList(
  props: CrossFieldErrorListProps,
): React.ReactElement {
  return (
    <ul data-component="cross-field-errors">
      {props.issues.map((it, i) => (
        <li
          key={`${it.path}-${i}`}
          data-error-level={it.level}
          data-error-path={it.path}
          style={{
            color: it.level === "error" ? "var(--state-fail, #c00)" : "var(--state-warn, #b80)",
          }}
        >
          [{it.level}] {it.path}: {it.message}
        </li>
      ))}
    </ul>
  );
}
