/**
 * Zod schema set consumed by the F22 hook factory family.
 *
 * Authoritative definition lives in design §6.2.4 (Data Model) plus per-feature
 * route bodies. In the long-term plan ``scripts/export_zod.py`` (Clarification
 * Addendum #1) regenerates this file from the backend pydantic models, but
 * for the F22 Green phase we hand-write the minimal surface the hooks consume.
 * Drift is caught by the F22 real-http integration tests against the
 * production ``harness.api:app`` (see ``test_f22_real_settings_consumer.py``).
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// Settings — IAPI-002 / IAPI-014 (F22 §IC Section A)
// ---------------------------------------------------------------------------
export const apiKeyRefSchema = z
  .object({
    service: z.string(),
    user: z.string(),
  })
  .nullable();

export const generalSettingsSchema = z
  .object({
    ui_density: z.string().optional(),
    keyring_backend: z.enum(["native", "keyrings.alt", "fail"]).optional(),
    api_key_ref: apiKeyRefSchema.optional(),
    api_key_masked: z.string().nullable().optional(),
    classifier: z
      .object({
        base_url: z.string().optional(),
        preset: z.string().optional(),
        provider: z.string().optional(),
        strict_schema_override: z.boolean().nullable().optional(),
        enabled: z.boolean().optional(),
      })
      .partial()
      .passthrough()
      .optional(),
  })
  .passthrough();

export type GeneralSettings = z.infer<typeof generalSettingsSchema>;

export const updateGeneralSettingsRequestSchema = z
  .object({
    api_key_plaintext: z.string().min(1).max(1024).optional(),
  })
  .passthrough();

export const testConnectionRequestSchema = z
  .object({
    base_url: z.string(),
    provider: z.string().optional(),
    model_name: z.string().optional(),
  })
  .passthrough();

export const testConnectionResultSchema = z
  .object({
    ok: z.boolean(),
    model: z.string().optional(),
    latency_ms: z.number().optional(),
    error: z.string().optional(),
  })
  .passthrough();

// ---------------------------------------------------------------------------
// Skills tree — IAPI-018 (F22 §IC Section B)
// ---------------------------------------------------------------------------
export interface SkillTreeNode {
  name: string;
  path: string;
  kind: "plugin" | "skill" | "file";
  children?: SkillTreeNode[];
}

export const skillTreeNodeSchema: z.ZodType<SkillTreeNode> = z.lazy(() =>
  z.object({
    name: z.string(),
    path: z.string(),
    kind: z.enum(["plugin", "skill", "file"]),
    children: z.array(skillTreeNodeSchema).optional(),
  }),
);

// Top-level can be either a node OR a `{root, plugins[]}` payload (legacy
// shape from F10). Accept both transparently — adapter normalises in the hook.
export const skillTreeResponseSchema = z.union([
  skillTreeNodeSchema,
  z
    .object({
      root: z.string().optional(),
      plugins: z.array(z.unknown()).optional(),
      name: z.string().optional(),
      kind: z.string().optional(),
      path: z.string().optional(),
      children: z.array(z.unknown()).optional(),
    })
    .passthrough(),
]);

export const skillsInstallRequestSchema = z
  .object({
    url: z.string(),
    target_dir: z.string().optional(),
  })
  .passthrough();

export const skillsInstallResultSchema = z
  .object({
    commit_sha: z.string().optional(),
  })
  .passthrough();

// ---------------------------------------------------------------------------
// Prompts (classifier prompt history) — F22 §IC Section B
// ---------------------------------------------------------------------------
export const promptHistoryEntrySchema = z
  .object({
    hash: z.string(),
    content_summary: z.string().optional(),
    created_at: z.string().optional(),
    author: z.string().optional(),
  })
  .passthrough();

export const classifierPromptSchema = z
  .object({
    current: z
      .object({
        content: z.string().default(""),
        hash: z.string().default(""),
      })
      .passthrough(),
    history: z.array(promptHistoryEntrySchema).default([]),
  })
  .passthrough();

export type ClassifierPrompt = z.infer<typeof classifierPromptSchema>;

// ---------------------------------------------------------------------------
// Files / Docs — IAPI-002 (F22 §IC Section C)
// ---------------------------------------------------------------------------
export const fileTreeEntrySchema = z
  .object({
    path: z.string(),
    kind: z.enum(["dir", "file"]),
    size: z.number().optional(),
  })
  .passthrough();

export const fileTreeSchema = z
  .object({
    root: z.string(),
    entries: z.array(fileTreeEntrySchema).default([]),
  })
  .passthrough();

export const fileContentSchema = z
  .object({
    path: z.string(),
    content: z.string(),
    encoding: z.string().default("utf-8"),
    truncated: z.boolean().optional(),
  })
  .passthrough();

// ---------------------------------------------------------------------------
// Validate — IAPI-016 (F22 §IC Section D)
// ---------------------------------------------------------------------------
export const validationIssueSchema = z
  .object({
    path: z.string(),
    level: z.enum(["error", "warning"]),
    message: z.string(),
  })
  .passthrough();

// Strict (non-passthrough) variant used by the schema-drift detector in
// process-files page; backend rename ``issues`` → ``errors`` is detected
// by the absence of ``issues`` in the parsed result, NOT by parse failure.
export const validationReportSchema = z.object({
  ok: z.boolean(),
  issues: z.array(validationIssueSchema),
  stderr_tail: z.string().optional(),
});

export type ValidationReport = z.infer<typeof validationReportSchema>;
export type ValidationIssue = z.infer<typeof validationIssueSchema>;

export const validateRequestSchema = z
  .object({
    path: z.string(),
    content: z.string(),
  })
  .passthrough();

// ---------------------------------------------------------------------------
// Git — IAPI-002 + IFR-005 (F22 §IC Section E)
// ---------------------------------------------------------------------------
export const gitCommitSchema = z
  .object({
    sha: z.string(),
    parents: z.array(z.string()).default([]),
    author: z.string().optional(),
    ts: z.string().optional(),
    committed_at: z.string().optional(),
    subject: z.string(),
    run_id: z.string().nullable().optional(),
    feature_id: z.union([z.number(), z.string()]).nullable().optional(),
  })
  .passthrough();

export const gitCommitsResponseSchema = z.array(gitCommitSchema);
export type GitCommit = z.infer<typeof gitCommitSchema>;

const diffLineSchema = z
  .object({
    type: z.enum(["add", "del", "context"]),
    content: z.string().default(""),
  })
  .passthrough();

const diffHunkSchema = z
  .object({
    old_start: z.number().optional(),
    old_lines: z.number().optional(),
    new_start: z.number().optional(),
    new_lines: z.number().optional(),
    header: z.string().optional(),
    lines: z.array(diffLineSchema).default([]),
  })
  .passthrough();

export const diffFileSchema = z
  .object({
    path: z.string(),
    kind: z.enum(["text", "binary"]),
    placeholder: z.boolean().optional(),
    hunks: z.array(diffHunkSchema).optional(),
  })
  .passthrough();

export const diffPayloadSchema = z
  .object({
    sha: z.string(),
    files: z.array(diffFileSchema).default([]),
  })
  .passthrough();

export type DiffPayload = z.infer<typeof diffPayloadSchema>;
export type DiffFile = z.infer<typeof diffFileSchema>;

// ---------------------------------------------------------------------------
// Process file schemas registry — F22 §IC `loadProcessFileSchema`
// ---------------------------------------------------------------------------
const featureItemSchema = z
  .object({
    id: z.number().int(),
    title: z.string().min(1, "title required"),
    srs_trace: z.array(z.string()).optional(),
    status: z.enum(["failing", "passing", "blocked"]).optional(),
    category: z.string().optional(),
    ui: z.boolean().optional(),
  })
  .passthrough();

const featureListSchema = z
  .object({
    features: z.array(featureItemSchema),
    constraints: z.array(z.string()).optional(),
    assumptions: z.array(z.string()).optional(),
    quality_gates: z
      .object({
        line_coverage_min: z.number().optional(),
        branch_coverage_min: z.number().optional(),
      })
      .passthrough()
      .optional(),
  })
  .passthrough();

export const processFileSchemas: Record<string, z.ZodTypeAny> = {
  "feature-list.json": featureListSchema,
  "env-guide.md": z.string(),
  "long-task-guide.md": z.string(),
  ".env.example": z.string(),
};
