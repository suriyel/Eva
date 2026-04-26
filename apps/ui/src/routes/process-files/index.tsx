/**
 * ProcessFilesPage — F22 §IC Section D · /process-files (UCD §4.7).
 *
 * Reads ``feature-list.json`` (default file) → renders ProcessFileForm with
 * the Zod schema; Save → POST /api/validate/feature-list.json; ok=false →
 * render CrossFieldErrorList; stderr_tail → dedicated panel.
 */
import * as React from "react";
import { useFileContent } from "../../api/routes/files";
import { useValidate, type ValidateResult } from "../../api/routes/validate";
import { loadProcessFileSchema } from "./load-schema";
import { ProcessFileForm } from "./components/process-file-form";
import { CrossFieldErrorList } from "./components/cross-field-error-list";

const DEFAULT_FILE = "feature-list.json";

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
  React.useEffect(() => {
    const raw = contentQ.data?.content;
    if (typeof raw === "string") {
      try {
        setDraft(JSON.parse(raw));
      } catch {
        setDraft({});
      }
    }
  }, [contentQ.data]);

  const onSave = (): void => {
    if (draft == null) return;
    validate.mutate({
      path: file,
      content: typeof draft === "string" ? draft : JSON.stringify(draft, null, 2),
    });
  };

  const result: ValidateResult | undefined = validate.data;
  const issues = result?.report?.issues ?? [];
  const stderrTail = result?.report?.stderr_tail;
  const schemaDrift = result?.schemaDrift === true;

  return (
    <div data-component="process-files-page">
      <h3>过程文件 — {file}</h3>
      {schema && draft != null ? (
        <ProcessFileForm
          file={file}
          schema={schema}
          value={draft}
          onChange={setDraft}
          onSave={onSave}
        />
      ) : (
        <div data-testid="process-file-loading">加载中…</div>
      )}
      {schemaDrift && (
        <div data-testid="process-file-schema-mismatch-banner" role="alert">
          后端 ValidationReport schema 漂移 — issues 字段缺失
        </div>
      )}
      {stderrTail && (
        <pre data-testid="process-file-stderr-tail" style={{ whiteSpace: "pre-wrap" }}>
          {stderrTail}
        </pre>
      )}
      {issues.length > 0 && <CrossFieldErrorList issues={issues} />}
    </div>
  );
}
