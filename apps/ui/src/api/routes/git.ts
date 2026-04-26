/**
 * Git commits / diff hooks — F22 §IC Section E.
 *
 * F22 NOTE: ``apiClient.fetch`` collapses 5xx → ``ServerError`` and discards
 * structured ``{detail:{code,...}}`` body. The 502 ``not_a_git_repo`` path
 * (IFR-005) is exactly the surface the FE must branch on. So this hook
 * issues the fetch directly and preserves the structured body via
 * ``HttpError.detail`` (matching the 4xx convention) so the page can read
 * ``error.code === 'not_a_git_repo'`` regardless of the HTTP status family.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiClient, HttpError, NetworkError, resolveApiBaseUrl } from "../client";
import { gitCommitsResponseSchema, diffPayloadSchema } from "../../lib/zod-schemas";
import type { z } from "zod";

type GitCommitList = z.infer<typeof gitCommitsResponseSchema>;
type DiffPayload = z.infer<typeof diffPayloadSchema>;

async function fetchGitJson<T>(path: string): Promise<T> {
  const url = `${resolveApiBaseUrl()}${path}`;
  let resp: Response;
  try {
    resp = await fetch(url, { method: "GET" });
  } catch (e) {
    throw new NetworkError(e instanceof Error ? e.message : String(e));
  }
  let body: unknown = null;
  try {
    const text = await resp.text();
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (resp.status >= 400) {
    // Promote both 4xx and 5xx to HttpError so the page can read structured detail.
    let code: string | null = null;
    if (body && typeof body === "object" && "detail" in (body as Record<string, unknown>)) {
      const inner = (body as { detail: unknown }).detail;
      if (inner && typeof inner === "object" && "code" in (inner as Record<string, unknown>)) {
        code = String((inner as { code: unknown }).code);
      }
    }
    throw new HttpError(resp.status, body, code);
  }
  return body as T;
}

export function useCommits(filter?: {
  run_id?: string;
  feature_id?: number;
}): UseQueryResult<GitCommitList> {
  return useQuery<GitCommitList, Error>({
    queryKey: ["GET", "/api/git/commits", filter ?? null],
    retry: false,
    queryFn: async () => {
      const qs: string[] = [];
      if (filter?.run_id) qs.push(`run_id=${encodeURIComponent(filter.run_id)}`);
      if (filter?.feature_id != null) qs.push(`feature_id=${filter.feature_id}`);
      const path = `/api/git/commits${qs.length ? `?${qs.join("&")}` : ""}`;
      const raw = await fetchGitJson<unknown>(path);
      return gitCommitsResponseSchema.parse(raw);
    },
  });
}

export function useDiff(sha: string | null): UseQueryResult<DiffPayload> {
  return useQuery<DiffPayload, Error>({
    queryKey: ["GET", "/api/git/diff", sha],
    enabled: typeof sha === "string" && sha.length >= 4,
    retry: false,
    queryFn: async () => {
      const raw = await apiClient.fetch<unknown>(
        "GET",
        `/api/git/diff/${encodeURIComponent(sha ?? "")}`,
      );
      return diffPayloadSchema.parse(raw);
    },
  });
}
