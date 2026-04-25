/**
 * HILCard —— HIL 问题卡片（pixel-equiv prototype `pages/HILInbox.jsx`）
 *
 * Traces §Visual Rendering Contract HILCard rows ·
 *        SRS FR-010 / FR-031 SEC / NFR-011（控件标注 chip "单选/多选/自由文本"）·
 *        Test Inventory T12..T16 / T18 / T40 / T44。
 *
 * SEC：freeform 文本经 React `{text}` 模板插槽 + `<textarea defaultValue={text}>`，
 *      不使用 dangerouslySetInnerHTML，不字符串拼接进 DOM。
 */
import * as React from "react";
import { Icons } from "@/components/icons";

export interface HilOption {
  label: string;
  desc?: string;
}

export type HilCardVariant =
  | "radio"
  | "checkbox"
  | "textarea"
  | "radio_with_freeform"
  | "checkbox_with_freeform";

export interface HilCardProps {
  ticketId: string;
  questionId: string;
  variant: HilCardVariant;
  question: string;
  options: HilOption[];
  phase: string;
  phaseColor?: string;
  answered?: boolean;
  defaultFreeformText?: string;
  onSubmit?: (selected: string[], freeformText: string | null) => void;
  submitting?: boolean;
}

const CONTROL_LABEL: Record<HilCardVariant, string> = {
  radio: "单选",
  checkbox: "多选",
  textarea: "自由文本",
  radio_with_freeform: "单选",
  checkbox_with_freeform: "多选",
};

interface RadioRowProps {
  option: HilOption;
  checked: boolean;
  kind: "radio" | "checkbox";
  onClick: () => void;
}

function RadioRow({ option, checked, kind, onClick }: RadioRowProps): React.ReactElement {
  const role = kind === "checkbox" ? "checkbox" : "radio";
  return (
    <div
      role={role}
      aria-checked={checked}
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "12px 14px",
        borderRadius: 6,
        cursor: "pointer",
        background: checked ? "var(--bg-active)" : "transparent",
        border: `1px solid ${checked ? "var(--accent)" : "var(--border-subtle)"}`,
        transition: "all 120ms",
      }}
    >
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: kind === "checkbox" ? 4 : "50%",
          border: `1.5px solid ${checked ? "var(--accent)" : "var(--border-strong)"}`,
          background: checked ? "var(--accent)" : "transparent",
          display: "grid",
          placeItems: "center",
          flex: "none",
          marginTop: 2,
        }}
      >
        {checked &&
          (kind === "checkbox" ? (
            <Icons.Check size={10} style={{ color: "var(--fg-on-accent)", strokeWidth: 3 }} />
          ) : (
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--fg-on-accent)",
              }}
            />
          ))}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 500, color: "var(--fg)" }}>{option.label}</div>
        {option.desc && (
          <div className="small" style={{ marginTop: 2, fontSize: 12, color: "var(--fg-mute)" }}>
            {option.desc}
          </div>
        )}
      </div>
    </div>
  );
}

export function HILCard(props: HilCardProps): React.ReactElement {
  const {
    ticketId,
    questionId,
    variant,
    question,
    options,
    phase,
    phaseColor = "var(--phase-design)",
    answered = false,
    defaultFreeformText = "",
    onSubmit,
    submitting = false,
  } = props;

  const isRadio = variant === "radio" || variant === "radio_with_freeform";
  const isCheckbox = variant === "checkbox" || variant === "checkbox_with_freeform";
  const isTextarea = variant === "textarea";
  const showFreeform =
    variant === "textarea" ||
    variant === "radio_with_freeform" ||
    variant === "checkbox_with_freeform";

  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [freeformText, setFreeformText] = React.useState<string>(defaultFreeformText);

  const toggle = React.useCallback(
    (label: string): void => {
      setSelected((prev) => {
        const next = new Set(prev);
        if (isRadio) {
          next.clear();
          next.add(label);
        } else {
          if (next.has(label)) next.delete(label);
          else next.add(label);
        }
        return next;
      });
    },
    [isRadio],
  );

  // happy-dom 的 GRADIENT_REGEXP `[^)]+` 拒绝 `var(--…)` 因含 `)` —— React 经
  // CSSOM 赋值会被吞，导致 style 属性为空。补一个 layout effect 直接 setAttribute
  // 写入 phase 色带 background，保证 prototype 等价 + 测试可观察（T16/T44）。
  // 真实浏览器 CSSOM 会覆盖此属性为同语义值，无视觉差异。
  const headerRef = React.useRef<HTMLElement | null>(null);
  React.useLayoutEffect(() => {
    if (!headerRef.current) return;
    const grad = `linear-gradient(90deg, ${phaseColor}14 0%, transparent 60%)`;
    const cur = headerRef.current.getAttribute("style") ?? "";
    if (!cur.includes("linear-gradient")) {
      headerRef.current.setAttribute("style", `${cur}background: ${grad}; background-image: ${grad};`);
    }
  }, [phaseColor]);

  const handleSubmit = (): void => {
    onSubmit?.(Array.from(selected), showFreeform ? freeformText : null);
  };

  return (
    <div
      data-component="hil-card"
      data-control={
        variant === "radio_with_freeform"
          ? "radio"
          : variant === "checkbox_with_freeform"
            ? "checkbox"
            : variant
      }
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border-subtle)",
        borderRadius: 8,
        overflow: "hidden",
        opacity: answered ? 0.5 : 1,
        minHeight: 220,
      }}
    >
      <header
        ref={headerRef}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 20px",
          borderBottom: "1px solid var(--border-subtle)",
          // background 由 useLayoutEffect 直接 setAttribute 注入（绕开 happy-dom
          // CSSOM 对 var() in linear-gradient 的拒绝）。生产环境 React 会保留同 CSS。
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 6,
            display: "grid",
            placeItems: "center",
            background: "rgba(245,181,68,0.12)",
            color: "var(--state-hil)",
          }}
        >
          <Icons.HelpCircle size={15} />
        </div>
        <span className="mono" style={{ fontSize: 11.5, color: "var(--fg-mute)" }}>
          {ticketId}
        </span>
        <span style={{ fontSize: 14.5, fontWeight: 600, color: "var(--fg)" }}>{question}</span>
        <span
          data-testid="control-label"
          style={{
            marginLeft: "auto",
            fontSize: 11,
            color: "var(--fg-dim)",
            padding: "2px 8px",
            borderRadius: 999,
            border: "1px solid var(--border-subtle)",
          }}
        >
          {CONTROL_LABEL[variant]}
        </span>
        <span
          data-testid="phase-chip"
          style={{
            fontSize: 11,
            color: phaseColor,
            padding: "2px 8px",
            borderRadius: 999,
            border: `1px solid ${phaseColor}44`,
          }}
        >
          Phase · {phase}
        </span>
      </header>
      <div style={{ padding: 20 }}>
        <div data-testid="question-id" hidden>
          {questionId}
        </div>
        {(isRadio || isCheckbox) && options.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {options.map((o, i) => (
              <RadioRow
                key={`${o.label}-${i}`}
                option={o}
                kind={isCheckbox ? "checkbox" : "radio"}
                checked={selected.has(o.label)}
                onClick={() => toggle(o.label)}
              />
            ))}
          </div>
        )}
        {showFreeform && (
          <div style={{ marginTop: isTextarea ? 0 : 16 }}>
            <div className="label" style={{ fontSize: 10.5, marginBottom: 6, color: "var(--fg-mute)" }}>
              你的回答
            </div>
            <textarea
              data-testid="hil-freeform"
              defaultValue={defaultFreeformText}
              onChange={(e) => setFreeformText(e.target.value)}
              style={{
                width: "100%",
                minHeight: 140,
                border: "1px solid var(--border)",
                borderRadius: 6,
                background: "var(--bg-inset)",
                padding: 12,
                fontFamily: "var(--font-mono)",
                fontSize: 13,
                color: "var(--fg)",
                resize: "vertical",
              }}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: 6,
                fontSize: 11,
                color: "var(--fg-mute)",
              }}
            >
              <span>Markdown 支持 · 引用 SRS 以 [FR-xxx]</span>
              <span className="mono">{freeformText.length} / 2000</span>
            </div>
          </div>
        )}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "12px 20px",
          borderTop: "1px solid var(--border-subtle)",
          background: "var(--bg-surface-alt, var(--bg-surface))",
        }}
      >
        <button
          type="button"
          data-testid="btn-submit-hil"
          onClick={handleSubmit}
          disabled={submitting || answered}
          style={{
            marginLeft: "auto",
            padding: "6px 12px",
            borderRadius: 6,
            background: submitting || answered ? "var(--border-subtle)" : "var(--accent)",
            color: "var(--fg-on-accent)",
            fontSize: 13,
            fontWeight: 600,
            border: "none",
            cursor: submitting || answered ? "not-allowed" : "pointer",
          }}
        >
          {submitting ? "提交中…" : "提交答复"}
        </button>
      </div>
    </div>
  );
}
