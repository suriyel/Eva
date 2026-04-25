/**
 * useTicketStreamFilters —— URL ?state=&tool=&run_id=&parent= ↔ filters 同步 hook
 *
 * Traces §Interface Contract `useTicketStreamFilters` ·
 *        §Test Inventory T37 / T38 ·
 *        Boundary Conditions URL filter 非法值 → cleanup。
 *
 * 行为：
 *   - 初始读 URL searchParams → filters
 *   - setFilter(key, value) → 写回 URL（保留其他 param；undefined 移除）
 *   - 非法 enum 值 → filter undefined 且 URL 自动清理
 */
import { useCallback, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

export type FilterKey = "state" | "tool" | "run_id" | "parent";

export interface TicketFilters {
  state?: string;
  tool?: string;
  run_id?: string;
  parent?: string;
}

const ALLOWED_VALUES: Partial<Record<FilterKey, ReadonlyArray<string>>> = {
  state: ["running", "completed", "failed", "hil_waiting", "paused", "cancelled"],
  tool: ["claude", "opencode", "cursor", "windsurf"],
};

function isAllowed(key: FilterKey, value: string): boolean {
  const allowed = ALLOWED_VALUES[key];
  if (!allowed) return value.length > 0 && value.length <= 256;
  return allowed.includes(value);
}

export interface UseTicketStreamFiltersResult {
  filters: TicketFilters;
  setFilter: (key: FilterKey, value: string | undefined) => void;
}

export function useTicketStreamFilters(): UseTicketStreamFiltersResult {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters: TicketFilters = useMemo(() => {
    const out: TicketFilters = {};
    for (const k of ["state", "tool", "run_id", "parent"] as FilterKey[]) {
      const raw = searchParams.get(k);
      if (raw == null) continue;
      if (isAllowed(k, raw)) {
        out[k] = raw;
      }
    }
    return out;
  }, [searchParams]);

  // Cleanup illegal values on first mount
  useEffect(() => {
    let dirty = false;
    const next = new URLSearchParams(searchParams);
    for (const k of ["state", "tool", "run_id", "parent"] as FilterKey[]) {
      const raw = next.get(k);
      if (raw != null && !isAllowed(k, raw)) {
        next.delete(k);
        dirty = true;
      }
    }
    if (dirty) {
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setFilter = useCallback(
    (key: FilterKey, value: string | undefined): void => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value === undefined || value === null || value === "") {
          next.delete(key);
        } else if (!isAllowed(key, value)) {
          next.delete(key);
        } else {
          next.set(key, value);
        }
        return next;
      });
    },
    [setSearchParams],
  );

  return { filters, setFilter };
}
