/**
 * Validate hook — F22 §IC Section D / IAPI-016.
 *
 * Notes
 * - The backend returns a permissive shape; we use ``safeParse`` here so the
 *   schema-drift detector in process-files can branch on the non-strict
 *   parse failure path instead of crashing the whole mutation chain.
 * - Subprocess crashes are surfaced as ``stderr_tail`` not ``throw`` (FR-039
 *   AC3). The hook never rejects on validator non-zero exit.
 */
import { useMutation, type UseMutationResult } from "@tanstack/react-query";
import { apiClient } from "../client";
import { validationReportSchema, type ValidationReport } from "../../lib/zod-schemas";

export interface ValidateRequest {
  path: string;
  content: string;
}

export interface ValidateResult {
  ok: boolean;
  report: ValidationReport | null;
  raw: unknown;
  schemaDrift: boolean;
}

export function useValidate(
  file: string,
): UseMutationResult<ValidateResult, Error, ValidateRequest> {
  return useMutation<ValidateResult, Error, ValidateRequest>({
    retry: false,
    mutationFn: async (req: ValidateRequest) => {
      const raw = await apiClient.fetch<unknown>(
        "POST",
        `/api/validate/${encodeURIComponent(file)}`,
        req,
      );
      const parsed = validationReportSchema.safeParse(raw);
      if (parsed.success) {
        return {
          ok: parsed.data.ok,
          report: parsed.data,
          raw,
          schemaDrift: false,
        };
      }
      // Schema drift — backend renamed a field. Surface it explicitly so the
      // page renders the schema-mismatch banner rather than silently passing.
      return { ok: false, report: null, raw, schemaDrift: true };
    },
  });
}
