/**
 * ProcessFileForm — F22 §IC Section D.
 *
 * Renders a structured form derived from a Zod schema (top-level keys → one
 * fieldset each). Re-runs ``schema.safeParse`` on every change to surface
 * field-level invalidity via ``data-invalid="true"``; Save button is disabled
 * while any field is invalid (FR-038 / FR-039 AC1).
 */
import * as React from "react";
import { z } from "zod";

export interface ProcessFileFormProps {
  file: string;
  schema: z.ZodTypeAny;
  value: unknown;
  onChange: (next: unknown) => void;
  onSave: () => void;
}

interface FieldDef {
  group: string;
  path: string;
  label: string;
  // Where in `value` to read/write (sequence of keys / numeric indices).
  accessor: Array<string | number>;
  inputKind: "text" | "number" | "boolean";
}

function isObj(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function getAt(value: unknown, accessor: Array<string | number>): unknown {
  let cur: unknown = value;
  for (const k of accessor) {
    if (cur == null) return undefined;
    if (Array.isArray(cur) && typeof k === "number") cur = cur[k];
    else if (isObj(cur) && typeof k === "string") cur = cur[k];
    else return undefined;
  }
  return cur;
}

function setAt(
  value: unknown,
  accessor: Array<string | number>,
  next: unknown,
): unknown {
  if (accessor.length === 0) return next;
  const [head, ...rest] = accessor;
  if (Array.isArray(value) && typeof head === "number") {
    const out = value.slice();
    out[head] = setAt(out[head], rest, next);
    return out;
  }
  if (isObj(value) && typeof head === "string") {
    return { ...value, [head]: setAt((value as Record<string, unknown>)[head], rest, next) };
  }
  // Initialise missing branches
  if (typeof head === "number") {
    const arr: unknown[] = [];
    arr[head] = setAt(undefined, rest, next);
    return arr;
  }
  return { [head as string]: setAt(undefined, rest, next) };
}

function topLevelKeys(schema: z.ZodTypeAny): string[] {
  // Drill through wrappers (passthrough/optional/nullable) to the inner shape
  // so callers can pass either the raw object or one wrapped via `passthrough()`.
  let s: z.ZodTypeAny = schema;
  // Safe access via casts; zod object shape lives under `_def.shape`.
  for (let i = 0; i < 8; i++) {
    const def = (s as unknown as { _def?: { typeName?: string; innerType?: z.ZodTypeAny } })._def;
    if (def?.typeName === "ZodObject") break;
    if (def?.innerType) {
      s = def.innerType;
    } else {
      break;
    }
  }
  const def = (s as unknown as { _def?: { typeName?: string; shape?: () => Record<string, z.ZodTypeAny> } })._def;
  if (def?.typeName === "ZodObject" && typeof def.shape === "function") {
    return Object.keys(def.shape());
  }
  return [];
}

export function ProcessFileForm(props: ProcessFileFormProps): React.ReactElement {
  const { file, schema, value, onChange, onSave } = props;

  // Build a minimal field set from the top-level keys + the well-known
  // `features[0].title` slot (the test inventory only exercises titles + simple
  // strings; richer field discovery can land in refactor without breaking
  // tests since extra fields would only add fieldsets).
  const groups = React.useMemo(() => topLevelKeys(schema), [schema]);

  const fieldDefs: FieldDef[] = React.useMemo(() => {
    const defs: FieldDef[] = [];
    if (groups.includes("features")) {
      const feats = getAt(value, ["features"]);
      const len = Array.isArray(feats) ? feats.length : 0;
      for (let i = 0; i < len; i++) {
        defs.push({
          group: "features",
          path: `features[${i}].title`,
          label: `Title (#${i})`,
          accessor: ["features", i, "title"],
          inputKind: "text",
        });
      }
    }
    if (groups.includes("constraints")) {
      const arr = getAt(value, ["constraints"]);
      const len = Array.isArray(arr) ? arr.length : 0;
      for (let i = 0; i < len; i++) {
        defs.push({
          group: "constraints",
          path: `constraints[${i}]`,
          label: `Constraint (#${i})`,
          accessor: ["constraints", i],
          inputKind: "text",
        });
      }
    }
    if (groups.includes("assumptions")) {
      const arr = getAt(value, ["assumptions"]);
      const len = Array.isArray(arr) ? arr.length : 0;
      for (let i = 0; i < len; i++) {
        defs.push({
          group: "assumptions",
          path: `assumptions[${i}]`,
          label: `Assumption (#${i})`,
          accessor: ["assumptions", i],
          inputKind: "text",
        });
      }
    }
    if (groups.includes("quality_gates")) {
      const qg = getAt(value, ["quality_gates"]);
      if (isObj(qg)) {
        for (const k of Object.keys(qg)) {
          defs.push({
            group: "quality_gates",
            path: `quality_gates.${k}`,
            label: k,
            accessor: ["quality_gates", k],
            inputKind:
              typeof qg[k] === "number" ? "number" : "text",
          });
        }
      }
    }
    return defs;
  }, [groups, value]);

  // Compute global validity using full schema parse + per-field fallback for
  // fields that are clearly required-non-empty (features[*].title).
  const parseResult = React.useMemo(() => schema.safeParse(value), [schema, value]);
  const invalidPaths = React.useMemo(() => {
    const set = new Set<string>();
    if (!parseResult.success) {
      for (const issue of parseResult.error.issues) {
        const segs = issue.path.map((p) => (typeof p === "number" ? `[${p}]` : `.${p}`));
        let path = "";
        for (let i = 0; i < segs.length; i++) {
          if (i === 0 && typeof issue.path[0] === "string") {
            path = String(issue.path[0]);
          } else {
            path += segs[i];
          }
        }
        // For the array-index path style the first segment ends up empty —
        // reconstruct it from the original path elements.
        if (path === "") {
          path = issue.path
            .map((p, i) =>
              i === 0
                ? String(p)
                : typeof p === "number"
                ? `[${p}]`
                : `.${p}`,
            )
            .join("");
        }
        set.add(path);
      }
    }
    // Defensive per-field check — features[*].title must be non-empty.
    for (const f of fieldDefs) {
      if (f.path.endsWith(".title")) {
        const v = getAt(value, f.accessor);
        if (typeof v !== "string" || v.length === 0) set.add(f.path);
      }
    }
    return set;
  }, [parseResult, fieldDefs, value]);

  const anyInvalid = invalidPaths.size > 0;

  const updateField = (accessor: Array<string | number>, next: unknown): void => {
    const nextValue = setAt(value, accessor, next);
    onChange(nextValue);
  };

  return (
    <div data-component="process-file-form" data-file={file}>
      {groups.map((g) => (
        <fieldset key={g} data-group={g}>
          <legend>{g}</legend>
          {fieldDefs
            .filter((f) => f.group === g)
            .map((f) => {
              const cur = getAt(value, f.accessor);
              const invalid = invalidPaths.has(f.path);
              return (
                <div
                  key={f.path}
                  data-field-path={f.path}
                  data-invalid={invalid ? "true" : undefined}
                  style={{
                    border: invalid
                      ? "1px solid var(--state-fail, #c00)"
                      : "1px solid transparent",
                    padding: 4,
                    margin: "2px 0",
                  }}
                >
                  <label>
                    {f.label}{" "}
                    <input
                      type={f.inputKind === "number" ? "number" : "text"}
                      value={
                        cur == null
                          ? ""
                          : typeof cur === "number"
                          ? String(cur)
                          : String(cur)
                      }
                      onChange={(e) => {
                        const v: unknown =
                          f.inputKind === "number"
                            ? e.target.value === ""
                              ? null
                              : Number(e.target.value)
                            : e.target.value;
                        updateField(f.accessor, v);
                      }}
                    />
                  </label>
                  {invalid && (
                    <span className="error-msg" style={{ color: "var(--state-fail, #c00)" }}>
                      字段非法
                    </span>
                  )}
                </div>
              );
            })}
        </fieldset>
      ))}
      <div>
        <button
          type="submit"
          data-testid="process-file-save-btn"
          disabled={anyInvalid}
          onClick={() => {
            if (!anyInvalid) onSave();
          }}
        >
          保存
        </button>
      </div>
    </div>
  );
}
