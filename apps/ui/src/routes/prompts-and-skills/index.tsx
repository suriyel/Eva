/**
 * PromptsAndSkillsPage — F22 §IC Section B · /skills (UCD §4.4).
 *
 * Composes:
 *   - SkillTreeViewer (readonly tree from useSkillTree)
 *   - Classifier prompt editor + history list (usePromptHistory + useUpdate*)
 *   - Skills install modal (file:// SEC reject, 22-37)
 */
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSkillTree, useSkillsInstall } from "../../api/routes/skills-tree";
import {
  usePromptHistory,
  useUpdateClassifierPrompt,
} from "../../api/routes/prompts-classifier";
import { HttpError } from "../../api/client";
import { SkillTreeViewer } from "./components/skill-tree-viewer";
import type { SkillTreeNode } from "../../lib/zod-schemas";

function normaliseTree(raw: unknown): SkillTreeNode {
  // Already SkillTreeNode shaped
  if (
    raw &&
    typeof raw === "object" &&
    "kind" in (raw as Record<string, unknown>) &&
    "name" in (raw as Record<string, unknown>)
  ) {
    const r = raw as SkillTreeNode;
    if (r.kind === "plugin" || r.kind === "skill" || r.kind === "file") {
      return r;
    }
  }
  // Legacy {root, plugins[]} shape from F10
  if (raw && typeof raw === "object" && "plugins" in (raw as Record<string, unknown>)) {
    const obj = raw as { root?: string; plugins?: Array<{ name?: string }> };
    const children: SkillTreeNode[] = (obj.plugins ?? []).map((p) => ({
      name: p.name ?? "?",
      path: p.name ?? "",
      kind: "plugin",
      children: [],
    }));
    return {
      name: "root",
      path: obj.root ?? "",
      kind: "plugin",
      children,
    };
  }
  return { name: "root", path: "", kind: "plugin", children: [] };
}

function describeHttpError(err: Error | null): string {
  if (!err) return "";
  if (err instanceof HttpError) {
    const detail = err.detail as { detail?: { code?: string; message?: string } } | unknown;
    if (
      detail !== null &&
      typeof detail === "object" &&
      "detail" in (detail as Record<string, unknown>)
    ) {
      const inner = (detail as { detail: unknown }).detail;
      if (inner && typeof inner === "object") {
        const obj = inner as { code?: string; message?: string };
        const parts = [obj.code, obj.message].filter(Boolean);
        if (parts.length > 0) return parts.join(": ");
      }
    }
    return `HTTP ${err.status}`;
  }
  return err.message || String(err);
}

export function PromptsAndSkillsPage(): React.ReactElement {
  const queryClient = useQueryClient();
  const treeQ = useSkillTree();
  const promptQ = usePromptHistory();
  const updatePrompt = useUpdateClassifierPrompt({
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["GET", "/api/prompts/classifier"] });
    },
  });
  const skillsInstall = useSkillsInstall();

  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState("");
  const [installOpen, setInstallOpen] = React.useState(false);
  const [installUrl, setInstallUrl] = React.useState("");
  const [selectedSkill, setSelectedSkill] = React.useState<string | null>(null);

  React.useEffect(() => {
    const cur = promptQ.data?.current?.content ?? "";
    if (!editing) setDraft(cur);
  }, [promptQ.data, editing]);

  const onSavePrompt = (): void => {
    updatePrompt.mutate(
      { content: draft },
      {
        onSuccess: () => setEditing(false),
      },
    );
  };

  const onSubmitInstall = (): void => {
    skillsInstall.mutate({ url: installUrl });
  };

  const tree = treeQ.data ? normaliseTree(treeQ.data) : null;
  const treeError = treeQ.error;
  const history = promptQ.data?.history ?? [];

  return (
    <div data-component="prompts-and-skills-page" style={{ display: "flex", gap: 16 }}>
      <div data-component="skills-pane" style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h3>Skills</h3>
          <button
            type="button"
            data-testid="skills-install-open-btn"
            onClick={() => setInstallOpen(true)}
          >
            安装/更新
          </button>
        </div>
        {treeError ? (
          <div data-testid="skill-tree-error-toast" role="alert">
            {describeHttpError(treeError)}
            <div data-component="skill-tree-viewer" />
          </div>
        ) : tree ? (
          <SkillTreeViewer tree={tree} onSelect={setSelectedSkill} />
        ) : (
          <div data-component="skill-tree-viewer" />
        )}
        {installOpen && (
          <div data-component="skills-install-modal" role="dialog">
            <label>
              URL{" "}
              <input
                data-testid="skills-install-url-input"
                value={installUrl}
                onChange={(e) => setInstallUrl(e.target.value)}
              />
            </label>
            <button
              type="button"
              data-testid="skills-install-submit-btn"
              onClick={onSubmitInstall}
            >
              提交
            </button>
            <button
              type="button"
              data-testid="skills-install-cancel-btn"
              onClick={() => setInstallOpen(false)}
            >
              取消
            </button>
            {skillsInstall.error && (
              <div data-testid="skills-install-error-toast" role="alert">
                {describeHttpError(skillsInstall.error)}
              </div>
            )}
          </div>
        )}
      </div>
      <div data-component="prompt-pane" style={{ flex: 1 }}>
        <h3>Classifier Prompt</h3>
        <div data-component="prompt-editor">
          {!editing ? (
            <>
              <pre data-testid="prompt-current">
                {promptQ.data?.current?.content ?? ""}
              </pre>
              <button
                type="button"
                data-testid="prompt-edit-btn"
                onClick={() => setEditing(true)}
              >
                编辑
              </button>
            </>
          ) : (
            <>
              <textarea
                data-testid="prompt-editor-textarea"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={6}
              />
              <button type="button" data-testid="prompt-save-btn" onClick={onSavePrompt}>
                保存
              </button>
              <button
                type="button"
                data-testid="prompt-cancel-btn"
                onClick={() => setEditing(false)}
              >
                取消
              </button>
            </>
          )}
        </div>
        {updatePrompt.error && (
          <div data-testid="prompt-save-error-toast" role="alert">
            {describeHttpError(updatePrompt.error)}
          </div>
        )}
        <h4>History</h4>
        <ul data-component="prompt-history">
          {history.map((h) => (
            <li
              key={h.hash}
              data-hash={h.hash}
              data-created-at={h.created_at}
            >
              {h.hash} · {h.content_summary ?? ""}
            </li>
          ))}
        </ul>
        {selectedSkill && <div data-testid="skill-selected">{selectedSkill}</div>}
      </div>
    </div>
  );
}
