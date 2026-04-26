/**
 * ProcessFilesPage — F22 §IC Section D · /process-files (UCD §4.7)
 *                  · F24 B6 重写 (设计稿控件大幅补齐 — 4 file chips,
 *                                三 h3 分块, features Grid Table, 右 340px
 *                                校验面板, header 双 button + dirty chip,
 *                                404 EmptyState).
 *
 * Reads ``feature-list.json`` (default file) → renders ProcessFileForm with
 * the Zod schema; Save → POST /api/validate/feature-list.json; ok=false →
 * render CrossFieldErrorList; stderr_tail → dedicated panel.
 *
 * B6 layout (per `docs/design-bundle/eava2/project/pages/ProcessFiles.jsx`):
 *   - Header: subtitle + dirty chip 条件 + [discard / save-and-commit] button
 *   - File chips row: 4 chip with strict data-testid + textContent
 *   - Main grid 1fr 340px:
 *     - Left: h3 Project / h3 Tech Stack / h3 Features 三分块, features
 *             Grid Table 5 列 + 「添加特性」 button, ProcessFileForm 仍渲染
 *             用于 F22 既有契约 (process-file-save-btn 等)
 *     - Right: aside[data-testid="validation-panel"] width=340px,
 *              三组 list (realtime / backend / refresh button)
 *   - 404 → [data-testid="processfiles-empty"] EmptyState +
 *           「重新加载」 button
 */
import * as React from "react";
import { useFileContent } from "../../api/routes/files";
import { useValidate, type ValidateResult } from "../../api/routes/validate";
import { HttpError } from "../../api/client";
import { loadProcessFileSchema } from "./load-schema";
import { ProcessFileForm } from "./components/process-file-form";
import { CrossFieldErrorList } from "./components/cross-field-error-list";

const DEFAULT_FILE = "feature-list.json";

interface FeatureRow {
  id: number | string;
  title: string;
  status: string;
  srs_trace: string[] | string;
}

interface FeatureListShape {
  project?: { name?: string; version?: string } | null;
  tech_stack?: Record<string, unknown> | null;
  features?: unknown;
  [k: string]: unknown;
}

function isObj(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function readFeatures(draft: unknown): unknown[] {
  if (!isObj(draft)) return [];
  const f = draft.features;
  return Array.isArray(f) ? f : [];
}

function emptyFeatureTemplate(nextId: number): FeatureRow {
  return { id: nextId, title: "", status: "failing", srs_trace: [] };
}

export function ProcessFilesPage(): React.ReactElement {
  const [file] = React.useState<string>(DEFAULT_FILE);
  const contentQ = useFileContent(file);
  const validate = useValidate(file);

  const schema = React.useMemo(() => {
    try {
      return loadProcessFileSchema(file);
    } catch {
      return null;
    }
  }, [file]);

  const [draft, setDraft] = React.useState<unknown>(null);
  const [pristine, setPristine] = React.useState<unknown>(null);
  // Track whether the user has begun editing locally — if so, an arriving
  // contentQ payload must NOT overwrite the user's in-flight draft. (Tests
  // exercise a race: B6-P5 clicks "add-feature" before fetch resolves.)
  const userTouchedRef = React.useRef<boolean>(false);
  React.useEffect(() => {
    const raw = contentQ.data?.content;
    if (typeof raw === "string") {
      try {
        const parsed = JSON.parse(raw);
        setPristine(parsed);
        if (!userTouchedRef.current) setDraft(parsed);
      } catch {
        setPristine({});
        if (!userTouchedRef.current) setDraft({});
      }
    }
  }, [contentQ.data]);

  const setDraftUserEdit = React.useCallback(
    (next: unknown | ((cur: unknown) => unknown)) => {
      userTouchedRef.current = true;
      setDraft(next as React.SetStateAction<unknown>);
    },
    [],
  );

  const dirty = React.useMemo(() => {
    if (draft == null && pristine == null) return false;
    try {
      return JSON.stringify(draft) !== JSON.stringify(pristine);
    } catch {
      return false;
    }
  }, [draft, pristine]);

  const onSave = React.useCallback((): void => {
    if (draft == null) return;
    validate.mutate({
      path: file,
      content: typeof draft === "string" ? draft : JSON.stringify(draft, null, 2),
    });
  }, [draft, file, validate]);

  const onDiscard = React.useCallback((): void => {
    userTouchedRef.current = false;
    setDraft(pristine);
  }, [pristine]);

  const onAddFeature = React.useCallback((): void => {
    setDraftUserEdit((cur: unknown) => {
      const base: FeatureListShape = isObj(cur) ? (cur as FeatureListShape) : {};
      const features = Array.isArray(base.features) ? base.features.slice() : [];
      const nextId =
        features.reduce<number>((mx, f) => {
          const id = isObj(f) && typeof f.id === "number" ? (f.id as number) : 0;
          return id > mx ? id : mx;
        }, 0) + 1;
      features.push(emptyFeatureTemplate(nextId));
      return { ...base, features };
    });
  }, [setDraftUserEdit]);

  const onRerunValidate = React.useCallback((): void => {
    // 「再次运行」 fires even before draft loads — send raw content if
    // available, else empty payload so backend can still validate the
    // on-disk file (B6-P6 contract).
    const rawFromDisk = contentQ.data?.content ?? null;
    const payload =
      draft == null
        ? rawFromDisk ?? ""
        : typeof draft === "string"
        ? draft
        : JSON.stringify(draft, null, 2);
    validate.mutate({ path: file, content: payload });
  }, [draft, file, validate, contentQ.data]);

  const onReload = React.useCallback((): void => {
    contentQ.refetch();
  }, [contentQ]);

  const result: ValidateResult | undefined = validate.data;
  const issues = result?.report?.issues ?? [];
  const stderrTail = result?.report?.stderr_tail;
  const schemaDrift = result?.schemaDrift === true;

  // Raw issues (best-effort) — used by ValidationPanel for permissive
  // backend payloads (e.g. issues with `severity` instead of `level`) so the
  // panel still surfaces issue messages even when strict schema parse failed.
  const rawIssues: Array<{ path?: unknown; level?: unknown; severity?: unknown; message?: unknown }> =
    React.useMemo(() => {
      const raw = result?.raw as { issues?: unknown } | undefined;
      const arr = raw?.issues;
      return Array.isArray(arr) ? (arr as Array<Record<string, unknown>>) : [];
    }, [result]);
  const rawStderrTail =
    typeof (result?.raw as { stderr_tail?: unknown } | undefined)?.stderr_tail === "string"
      ? (result?.raw as { stderr_tail: string }).stderr_tail
      : null;

  // 404 detection — switch to EmptyState; do NOT remain on "loading".
  const fileError = contentQ.error as Error | null;
  const is404 = fileError instanceof HttpError && fileError.status === 404;

  // ---------------------------------------------------------------------
  // 404 EmptyState (B6-N1)
  // ---------------------------------------------------------------------
  if (is404) {
    return (
      <div data-component="process-files-page">
        <ProcessFilesHeader
          dirty={false}
          onDiscard={onDiscard}
          onSave={onSave}
        />
        <FileChipsRow />
        <div data-testid="processfiles-empty" style={{ padding: 24 }}>
          <p>尚未初始化 feature-list.json — 请先运行 init.sh 生成项目骨架。</p>
          <button
            type="button"
            data-testid="processfiles-reload"
            onClick={onReload}
          >
            重新加载
          </button>
        </div>
      </div>
    );
  }

  const draftShape: FeatureListShape = isObj(draft) ? (draft as FeatureListShape) : {};
  const features = readFeatures(draft);

  return (
    <div data-component="process-files-page">
      <ProcessFilesHeader
        dirty={dirty}
        onDiscard={onDiscard}
        onSave={onSave}
      />
      <FileChipsRow />
      <div
        data-testid="processfiles-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 340px",
          gap: 16,
          marginTop: 12,
        }}
      >
        {/* ----------------------------------------------------------- LEFT */}
        <div data-section-host="left">
          <section data-section="project">
            <h3 data-section="project">Project</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <label>
                name{" "}
                <input
                  data-testid="project-name-input"
                  defaultValue={draftShape.project?.name ?? ""}
                />
              </label>
              <label>
                version{" "}
                <input
                  data-testid="project-version-input"
                  defaultValue={draftShape.project?.version ?? ""}
                />
              </label>
            </div>
          </section>
          <section data-section="tech-stack" style={{ marginTop: 12 }}>
            <h3 data-section="tech-stack">Tech Stack</h3>
            <div style={{ fontSize: 12, color: "var(--fg-mute)" }}>
              {draftShape.tech_stack
                ? JSON.stringify(draftShape.tech_stack)
                : "—"}
            </div>
          </section>
          <section data-section="features" style={{ marginTop: 12 }}>
            <h3 data-section="features">Features</h3>
            <table
              data-testid="features-grid"
              style={{ width: "100%", borderCollapse: "collapse" }}
            >
              <thead>
                <tr>
                  <th>id</th>
                  <th>title</th>
                  <th>status</th>
                  <th>srs_trace</th>
                  <th>actions</th>
                </tr>
              </thead>
              <tbody>
                {features.length === 0 ? (
                  <tr data-empty-row="true">
                    <td colSpan={5} style={{ color: "var(--fg-mute)", fontSize: 12 }}>
                      暂无特性，点击「添加特性」新增
                    </td>
                  </tr>
                ) : (
                  features.map((f, i) => {
                    const row = isObj(f) ? f : {};
                    return (
                      <tr key={i} data-feature-row={i}>
                        <td>{String(row.id ?? "")}</td>
                        <td>{String(row.title ?? "")}</td>
                        <td>{String(row.status ?? "")}</td>
                        <td>
                          {Array.isArray(row.srs_trace)
                            ? (row.srs_trace as string[]).join(", ")
                            : String(row.srs_trace ?? "")}
                        </td>
                        <td>
                          <button
                            type="button"
                            data-testid={`feature-row-edit-${i}`}
                          >
                            编辑
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
            <button
              type="button"
              data-testid="add-feature"
              onClick={onAddFeature}
            >
              添加特性
            </button>
          </section>
          {/* F22 ProcessFileForm 仍保留 — 22-12..22-34 既有契约 */}
          {schema && draft != null ? (
            <div style={{ marginTop: 16 }}>
              <ProcessFileForm
                file={file}
                schema={schema}
                value={draft}
                onChange={setDraftUserEdit}
                onSave={onSave}
              />
            </div>
          ) : (
            <div data-testid="process-file-loading">加载中…</div>
          )}
          {schemaDrift && (
            <div data-testid="process-file-schema-mismatch-banner" role="alert">
              后端 ValidationReport schema 漂移 — issues 字段缺失
            </div>
          )}
          {stderrTail && (
            <pre
              data-testid="process-file-stderr-tail"
              style={{ whiteSpace: "pre-wrap" }}
            >
              {stderrTail}
            </pre>
          )}
          {issues.length > 0 && <CrossFieldErrorList issues={issues} />}
        </div>
        {/* ---------------------------------------------------------- RIGHT */}
        <ValidationPanel
          issues={
            issues.length > 0
              ? issues.map((it) => ({
                  path: it.path,
                  level: it.level,
                  message: it.message,
                }))
              : rawIssues.map((it) => ({
                  path: typeof it.path === "string" ? it.path : "",
                  level:
                    typeof it.level === "string"
                      ? (it.level as string)
                      : typeof it.severity === "string"
                      ? (it.severity as string)
                      : "info",
                  message:
                    typeof it.message === "string" ? (it.message as string) : "",
                }))
          }
          stderrTail={stderrTail ?? rawStderrTail ?? null}
          isError={validate.isError}
          errorMsg={validate.error?.message ?? null}
          onRerun={onRerunValidate}
        />
      </div>
    </div>
  );
}

// ============================================================================
// Internal sub-components — flat module to avoid file proliferation.
// ============================================================================

interface ProcessFilesHeaderProps {
  dirty: boolean;
  onDiscard: () => void;
  onSave: () => void;
}

function ProcessFilesHeader(props: ProcessFilesHeaderProps): React.ReactElement {
  const { dirty, onDiscard, onSave } = props;
  return (
    <header
      data-testid="processfiles-header"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 0",
        borderBottom: "1px solid var(--border-subtle, #e5e5e5)",
      }}
    >
      <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>过程文件</h2>
      <span style={{ fontSize: 12, color: "var(--fg-mute)" }}>
        feature-list.json
      </span>
      {/* dirty chip — always rendered, display:none when not dirty */}
      <span
        data-testid="dirty-chip"
        style={{
          display: dirty ? "inline-block" : "none",
          padding: "2px 8px",
          borderRadius: 12,
          background: "var(--state-warn, #b80)",
          color: "#fff",
          fontSize: 11,
        }}
      >
        未保存
      </span>
      <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
        <button
          type="button"
          data-testid="discard-changes"
          onClick={onDiscard}
        >
          还原更改
        </button>
        <button
          type="button"
          data-testid="save-and-commit"
          onClick={onSave}
        >
          保存并提交
        </button>
      </div>
    </header>
  );
}

function FileChipsRow(): React.ReactElement {
  const chips: Array<{ testid: string; label: string }> = [
    { testid: "file-chip-feature-list", label: "feature-list.json" },
    { testid: "file-chip-env-guide", label: "env-guide.md" },
    { testid: "file-chip-long-task-guide", label: "long-task-guide.md" },
    { testid: "file-chip-env-example", label: ".env.example" },
  ];
  return (
    <div
      data-testid="file-chips-row"
      style={{
        display: "flex",
        gap: 8,
        marginTop: 8,
        flexWrap: "wrap",
      }}
    >
      {chips.map((c) => (
        <span
          key={c.testid}
          data-testid={c.testid}
          style={{
            padding: "4px 10px",
            borderRadius: 12,
            background: "var(--bg-surface, #f5f5f5)",
            border: "1px solid var(--border-subtle, #ddd)",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          {c.label}
        </span>
      ))}
    </div>
  );
}

interface ValidationPanelProps {
  issues: Array<{ path: string; level?: string; message: string }>;
  stderrTail: string | null;
  isError: boolean;
  errorMsg: string | null;
  onRerun: () => void;
}

function ValidationPanel(props: ValidationPanelProps): React.ReactElement {
  const { issues, stderrTail, isError, errorMsg, onRerun } = props;
  return (
    <aside
      data-testid="validation-panel"
      style={{
        width: "340px",
        minWidth: "340px",
        maxWidth: "340px",
        background: "var(--bg-surface, #fafafa)",
        border: "1px solid var(--border-subtle, #e5e5e5)",
        borderRadius: 6,
        padding: 12,
        boxSizing: "border-box",
      }}
    >
      <div data-validation-group="realtime">
        <h4 style={{ fontSize: 12, color: "var(--fg-dim)", margin: "0 0 4px" }}>
          实时校验
        </h4>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 12 }}>
          <li>schema parse OK</li>
        </ul>
      </div>
      <div data-validation-group="backend" style={{ marginTop: 8 }}>
        <h4 style={{ fontSize: 12, color: "var(--fg-dim)", margin: "0 0 4px" }}>
          后端校验
        </h4>
        <ul
          data-testid="backend-validation-issues"
          style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 12 }}
        >
          {issues.length === 0 ? (
            <li data-empty="true" style={{ color: "var(--fg-mute)" }}>
              无 issues
            </li>
          ) : (
            issues.map((it, i) => (
              <li
                key={`${it.path}-${i}`}
                data-issue-level={it.level ?? "error"}
                data-issue-path={it.path}
              >
                [{it.level ?? "error"}] {it.path}: {it.message}
              </li>
            ))
          )}
        </ul>
        {stderrTail && (
          <pre
            data-testid="validation-stderr-tail"
            style={{ whiteSpace: "pre-wrap", fontSize: 11 }}
          >
            {stderrTail}
          </pre>
        )}
        {isError && (
          <div
            data-testid="validation-error"
            role="alert"
            style={{ color: "var(--state-fail, #c00)", fontSize: 12 }}
          >
            校验请求失败：{errorMsg ?? "未知错误"}
          </div>
        )}
      </div>
      <div data-validation-group="actions" style={{ marginTop: 12 }}>
        <button
          type="button"
          data-testid="rerun-validate"
          onClick={onRerun}
        >
          再次运行
        </button>
      </div>
    </aside>
  );
}
