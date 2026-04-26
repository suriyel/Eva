/**
 * MaskedKeyInput — F22 §IC Section A.
 *
 * NFR-008: plaintext lives only inside this component's local ``draft`` state
 * for the duration of the change → submit cycle. After the parent commits the
 * mutation we reset draft to '' so React DevTools props no longer carry the
 * plaintext substring (covered by 22-44 audit-log scan).
 */
import * as React from "react";

export interface MaskedKeyInputProps {
  masked: string | null;
  onSubmitPlaintext: (s: string) => void;
  disabled?: boolean;
}

export function MaskedKeyInput(props: MaskedKeyInputProps): React.ReactElement {
  const { masked, onSubmitPlaintext, disabled } = props;
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState("");

  const submit = (): void => {
    if (!draft) return;
    onSubmitPlaintext(draft);
    setDraft("");
    setEditing(false);
  };

  if (masked === null || masked === "") {
    return (
      <div data-component="masked-key-input">
        <span data-testid="masked-key-empty">未配置</span>
      </div>
    );
  }

  return (
    <div data-component="masked-key-input">
      {!editing ? (
        <>
          <span data-testid="masked-key-value">{masked}</span>
          <button
            type="button"
            data-testid="masked-key-change-btn"
            disabled={disabled}
            onClick={() => {
              setDraft("");
              setEditing(true);
            }}
          >
            更换
          </button>
        </>
      ) : (
        <>
          <input
            type="password"
            data-testid="masked-key-plaintext-input"
            value={draft}
            disabled={disabled}
            onChange={(e) => setDraft(e.target.value)}
          />
          <button
            type="button"
            data-testid="masked-key-submit-btn"
            disabled={disabled}
            onClick={submit}
          >
            保存
          </button>
          <button
            type="button"
            data-testid="masked-key-cancel-btn"
            onClick={() => {
              setDraft("");
              setEditing(false);
            }}
          >
            取消
          </button>
        </>
      )}
    </div>
  );
}
