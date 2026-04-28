/**
 * WorkdirPicker — Workspace 切换器（chip + dropdown）。
 *
 * - 显示当前 ``current_workdir`` 的 basename（无则显示"选择工作目录"）。
 * - dropdown 列出全量 ``workdirs``，点击切换；行尾 × 移除。
 * - 底部 "+ 新增工作目录" 调 ``pickNativeWorkdir``：桌面壳走原生 FOLDER_DIALOG，
 *   Web 模式 fallback 文本输入对话框（粘贴绝对路径）。
 */
import * as React from "react";
import { useQueryClient, QueryClientContext } from "@tanstack/react-query";
import { Icons } from "./icons";
import {
  useWorkdirs,
  useSelectWorkdir,
  useRemoveWorkdir,
  pickNativeWorkdir,
} from "../api/routes/workdirs";

function basename(p: string): string {
  if (!p) return "";
  const trimmed = p.replace(/[\\/]+$/, "");
  const idx = Math.max(trimmed.lastIndexOf("/"), trimmed.lastIndexOf("\\"));
  return idx >= 0 ? trimmed.slice(idx + 1) : trimmed;
}

interface WorkdirPickerProps {
  collapsed?: boolean;
}

interface TextInputModalProps {
  onSubmit: (path: string) => void;
  onCancel: () => void;
  errorMessage?: string | null;
}

function TextInputModal({ onSubmit, onCancel, errorMessage }: TextInputModalProps) {
  const [value, setValue] = React.useState("");

  return (
    <div
      data-testid="workdir-text-input-modal"
      role="dialog"
      aria-label="输入工作目录绝对路径"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.55)",
        display: "grid",
        placeItems: "center",
        zIndex: 1000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        style={{
          width: 480,
          maxWidth: "90vw",
          padding: 20,
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: 8,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600 }}>新增工作目录</div>
        <div style={{ fontSize: 12, color: "var(--fg-dim)" }}>
          请粘贴绝对路径，例如 <code>/home/user/code/myproject</code>
        </div>
        <input
          autoFocus
          type="text"
          value={value}
          placeholder="/absolute/path/to/repo"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && value.trim()) {
              onSubmit(value.trim());
            } else if (e.key === "Escape") {
              onCancel();
            }
          }}
          style={{
            padding: "8px 10px",
            borderRadius: 4,
            border: "1px solid var(--border-subtle)",
            background: "var(--bg-app)",
            color: "var(--fg)",
            fontSize: 13,
            fontFamily: "var(--font-mono)",
          }}
        />
        {errorMessage && (
          <div style={{ fontSize: 12, color: "var(--state-fail)" }}>{errorMessage}</div>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onCancel}
            style={{
              padding: "6px 14px",
              borderRadius: 4,
              border: "1px solid var(--border-subtle)",
              background: "transparent",
              color: "var(--fg)",
              cursor: "pointer",
            }}
          >
            取消
          </button>
          <button
            type="button"
            disabled={!value.trim()}
            onClick={() => onSubmit(value.trim())}
            style={{
              padding: "6px 14px",
              borderRadius: 4,
              border: "1px solid var(--accent)",
              background: "var(--accent)",
              color: "#0A0D12",
              cursor: value.trim() ? "pointer" : "not-allowed",
              opacity: value.trim() ? 1 : 0.5,
            }}
          >
            确定
          </button>
        </div>
      </div>
    </div>
  );
}

export function WorkdirPicker({
  collapsed = false,
}: WorkdirPickerProps): React.ReactElement | null {
  const hasQueryClient = React.useContext(QueryClientContext) !== undefined;
  if (!hasQueryClient) return null;
  return <WorkdirPickerInner collapsed={collapsed} />;
}

function WorkdirPickerInner({ collapsed }: { collapsed: boolean }): React.ReactElement {
  const queryClient = useQueryClient();
  const workdirsQ = useWorkdirs();
  const selectMut = useSelectWorkdir();
  const removeMut = useRemoveWorkdir();

  const [open, setOpen] = React.useState(false);
  const [textInputOpen, setTextInputOpen] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const wrapperRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const invalidateAfterMutation = (): void => {
    queryClient.invalidateQueries({ queryKey: ["GET", "/api/workdirs"] });
    queryClient.invalidateQueries({ queryKey: ["GET", "/api/runs/current"] });
    queryClient.invalidateQueries({ queryKey: ["GET", "/api/runs"] });
  };

  const submitPath = async (path: string): Promise<void> => {
    setSubmitError(null);
    try {
      await selectMut.mutateAsync({ path });
      invalidateAfterMutation();
      setTextInputOpen(false);
      setOpen(false);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleAdd = async (): Promise<void> => {
    setSubmitError(null);
    try {
      const outcome = await pickNativeWorkdir();
      if (outcome.ok) {
        if (outcome.path) {
          await submitPath(outcome.path);
        }
      } else {
        // Web 模式 → 文本输入 fallback
        setTextInputOpen(true);
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleSelect = async (path: string): Promise<void> => {
    if (path === workdirsQ.data?.current) {
      setOpen(false);
      return;
    }
    await submitPath(path);
  };

  const handleRemove = async (path: string): Promise<void> => {
    if (!window.confirm(`从工作区列表移除\n${path} ?`)) return;
    try {
      await removeMut.mutateAsync({ path });
      invalidateAfterMutation();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    }
  };

  const current = workdirsQ.data?.current ?? null;
  const items = workdirsQ.data?.workdirs ?? [];
  const chipLabel = current ? basename(current) : "选择工作目录";

  return (
    <div
      ref={wrapperRef}
      data-testid="workdir-picker"
      style={{
        padding: collapsed ? "8px" : "8px 16px",
        borderBottom: "1px solid var(--border-subtle)",
        position: "relative",
      }}
    >
      <button
        type="button"
        data-testid="workdir-picker-chip"
        title={current ?? "选择工作目录"}
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 8,
          height: 36,
          padding: "0 10px",
          borderRadius: 4,
          background: "var(--bg-app)",
          border: "1px solid var(--border-subtle)",
          color: "var(--fg)",
          cursor: "pointer",
          fontSize: 12,
          textAlign: "left",
        }}
      >
        <Icons.FolderOpen size={14} />
        {!collapsed && (
          <>
            <span
              style={{
                flex: 1,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {chipLabel}
            </span>
            <Icons.ChevronDown size={14} />
          </>
        )}
      </button>

      {open && !collapsed && (
        <div
          data-testid="workdir-picker-dropdown"
          style={{
            position: "absolute",
            top: "100%",
            left: 16,
            right: 16,
            marginTop: 4,
            background: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            borderRadius: 6,
            boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
            zIndex: 50,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {items.length === 0 ? (
            <div style={{ padding: 12, fontSize: 12, color: "var(--fg-mute)" }}>
              尚无工作目录
            </div>
          ) : (
            items.map((p) => {
              const active = p === current;
              return (
                <div
                  key={p}
                  data-testid="workdir-row"
                  data-active={active ? "true" : "false"}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 10px",
                    borderBottom: "1px solid var(--border-subtle)",
                    fontSize: 12,
                    background: active ? "var(--bg-active)" : "transparent",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      void handleSelect(p);
                    }}
                    title={p}
                    style={{
                      flex: 1,
                      textAlign: "left",
                      background: "transparent",
                      border: "none",
                      color: "var(--fg)",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      padding: "2px 0",
                    }}
                  >
                    <span style={{ fontWeight: active ? 600 : 400 }}>{basename(p)}</span>
                    <span
                      style={{
                        marginLeft: 6,
                        color: "var(--fg-mute)",
                        fontSize: 11,
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {p}
                    </span>
                  </button>
                  <button
                    type="button"
                    aria-label="移除"
                    title="移除"
                    onClick={() => {
                      void handleRemove(p);
                    }}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "var(--fg-dim)",
                      cursor: "pointer",
                      padding: 4,
                    }}
                  >
                    <Icons.X size={12} />
                  </button>
                </div>
              );
            })
          )}
          <button
            type="button"
            data-testid="workdir-picker-add"
            onClick={() => {
              void handleAdd();
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 10px",
              background: "transparent",
              border: "none",
              color: "var(--accent)",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            <Icons.Plus size={12} /> 新增工作目录
          </button>
          {submitError && (
            <div
              style={{
                padding: "6px 10px",
                fontSize: 11,
                color: "var(--state-fail)",
                borderTop: "1px solid var(--border-subtle)",
              }}
            >
              {submitError}
            </div>
          )}
        </div>
      )}

      {textInputOpen && (
        <TextInputModal
          errorMessage={submitError}
          onSubmit={(path) => {
            void submitPath(path);
          }}
          onCancel={() => {
            setTextInputOpen(false);
            setSubmitError(null);
          }}
        />
      )}
    </div>
  );
}
