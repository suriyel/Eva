/**
 * useCurrentRun — F24 B2 helper hook returning the active run id from
 * GET /api/runs/current.
 *
 * Returns ``null`` when the backend reports no active run (404 or 200/null).
 * 4xx errors other than 404 are surfaced via the query result so callers may
 * branch on ``query.error``; null current_run is the typical pre-Start state
 * and must NOT be propagated as an error.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { resolveApiBaseUrl } from "../client";

export interface CurrentRun {
  run_id: string;
  state: string;
}

export function useCurrentRun(): UseQueryResult<CurrentRun | null> {
  return useQuery<CurrentRun | null>({
    queryKey: ["GET", "/api/runs/current"],
    retry: false,
    queryFn: async () => {
      const resp = await fetch(`${resolveApiBaseUrl()}/api/runs/current`);
      if (resp.status === 404) return null;
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      if (!text || text === "null") return null;
      return JSON.parse(text) as CurrentRun;
    },
  });
}

export function useCurrentRunId(): string | null {
  const q = useCurrentRun();
  return q.data?.run_id ?? null;
}
