/**
 * RunOverviewPage —— "/" 路由首屏
 *
 * Traces §Interface Contract `RunOverviewPage` / `pauseRun` / `cancelRun` ·
 *        §Test Inventory T01 / T02 / T29 / T31 / T32 / T33 / T34 ·
 *        §Visual Rendering Contract phase-stepper / metrics-card / Empty State ·
 *        SRS FR-030 AC-1（6 元素 + cost 总和）+ AC-2（work N/M）。
 *
 * 6 元素：phase-stepper / current-skill / current-feature / run-cost / run-turns / run-head。
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useWs } from "@/ws/use-ws";
import { PhaseStepper } from "@/components/phase-stepper";
import { Icons } from "@/components/icons";
import { resolveApiBaseUrl } from "@/api/client";
import {
  useWorkdirs,
  useSelectWorkdir,
  pickNativeWorkdir,
} from "@/api/routes/workdirs";
import {
  runOverviewReducer,
  type RunStatus,
  type RunEvent,
  type RunPhase,
} from "./run-status-reducer";

const PHASE_INDEX: Record<RunPhase, number> = {
  requirements: 0,
  ucd: 1,
  design: 2,
  ats: 3,
  init: 4,
  work: 5,
  st: 6,
  finalize: 7,
};

export type RunControlErrorCode =
  | "RUN_NOT_FOUND"
  | "STATE_CONFLICT"
  | "BAD_REQUEST"
  | "NETWORK_ERROR";

export class RunControlError extends Error {
  public readonly code: RunControlErrorCode;
  constructor(code: RunControlErrorCode, message: string) {
    super(message);
    this.name = "RunControlError";
    this.code = code;
    Object.setPrototypeOf(this, RunControlError.prototype);
  }
}

async function postRunControl(
  runId: string,
  action: "pause" | "cancel",
): Promise<RunStatus> {
  if (!runId) throw new RunControlError("BAD_REQUEST", "runId required");
  const url = `${resolveApiBaseUrl()}/api/runs/${runId}/${action}`;
  let resp: Response;
  try {
    resp = await fetch(url, { method: "POST" });
  } catch (e) {
    throw new RunControlError(
      "NETWORK_ERROR",
      e instanceof Error ? e.message : String(e),
    );
  }
  if (resp.status === 404) throw new RunControlError("RUN_NOT_FOUND", "HTTP 404");
  if (resp.status === 409) throw new RunControlError("STATE_CONFLICT", "HTTP 409");
  if (resp.status >= 400) throw new RunControlError("BAD_REQUEST", `HTTP ${resp.status}`);
  const text = await resp.text();
  return text ? (JSON.parse(text) as RunStatus) : ({} as RunStatus);
}

/** Pause a run via IAPI-002 POST /api/runs/:id/pause（§Interface Contract `pauseRun`）. */
export async function pauseRun(runId: string): Promise<RunStatus> {
  return postRunControl(runId, "pause");
}

/** Cancel a run via IAPI-002 POST /api/runs/:id/cancel（§Interface Contract `cancelRun`）. */
export async function cancelRun(runId: string): Promise<RunStatus> {
  return postRunControl(runId, "cancel");
}

export function RunOverviewPage(): React.ReactElement {
  const queryClient = useQueryClient();
  const runQ = useQuery<RunStatus | null>({
    queryKey: ["GET", "/api/runs/current"],
    retry: false,
    queryFn: async () => {
      const resp = await fetch(`${resolveApiBaseUrl()}/api/runs/current`);
      if (resp.status === 404) return null;
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      if (!text || text === "null") return null;
      return JSON.parse(text) as RunStatus;
    },
  });

  const [liveStatus, setLiveStatus] = React.useState<RunStatus | null>(null);
  const [controlError, setControlError] = React.useState<{ code: string; message: string } | null>(
    null,
  );
  const workdirsQ = useWorkdirs();
  const selectWorkdirMut = useSelectWorkdir();
  const currentWorkdir = workdirsQ.data?.current ?? null;
  // F24 B1 — useStartRun (POST /api/runs/start) wraps the Start button click.
  const startRun = useMutation<RunStatus, Error, string>({
    retry: false,
    mutationFn: async (workdir: string) => {
      const resp = await fetch(`${resolveApiBaseUrl()}/api/runs/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workdir }),
      });
      if (!resp.ok) {
        const text = await resp.text();
        let detail = text;
        try {
          const parsed = JSON.parse(text);
          detail =
            (parsed?.detail?.message as string) ??
            (typeof parsed?.detail === "string" ? parsed.detail : text);
        } catch {
          /* keep raw */
        }
        throw new RunControlError(
          resp.status === 409 ? "STATE_CONFLICT" : "BAD_REQUEST",
          `HTTP ${resp.status}: ${detail}`,
        );
      }
      const text = await resp.text();
      const parsed = (text ? JSON.parse(text) : {}) as RunStatus;
      return parsed;
    },
    onSuccess: (data) => {
      if (data && typeof data === "object" && (data as { run_id?: string }).run_id) {
        setLiveStatus(data);
      }
      queryClient.invalidateQueries({ queryKey: ["GET", "/api/runs/current"] });
    },
    onError: (err) => {
      const e = err as RunControlError;
      setControlError({ code: e.code ?? "BAD_REQUEST", message: e.message ?? "" });
    },
  });
  const handleStart = React.useCallback(async (): Promise<void> => {
    if (startRun.isPending) return;
    setControlError(null);
    let target = currentWorkdir;
    if (!target) {
      // 未选 workdir → 触发文件夹选择（桌面壳 native; web 无 fallback 则提示用户去 sidebar）
      try {
        const outcome = await pickNativeWorkdir();
        if (outcome.ok) {
          if (!outcome.path) return; // 用户取消
          await selectWorkdirMut.mutateAsync({ path: outcome.path });
          queryClient.invalidateQueries({ queryKey: ["GET", "/api/workdirs"] });
          target = outcome.path;
        } else {
          setControlError({
            code: "NO_WORKDIR",
            message: "请在左侧 Workspace 选择器选择工作目录后再启动",
          });
          return;
        }
      } catch (err) {
        setControlError({
          code: "BAD_REQUEST",
          message: err instanceof Error ? err.message : String(err),
        });
        return;
      }
    }
    if (target) startRun.mutate(target);
  }, [startRun, currentWorkdir, selectWorkdirMut, queryClient]);

  // sync server query into local state
  React.useEffect(() => {
    if (runQ.data === undefined) return;
    setLiveStatus(runQ.data);
  }, [runQ.data]);

  const runId = liveStatus?.run_id ?? null;

  const onWsEvent = React.useCallback((ev: { kind: string; payload?: unknown }) => {
    if (!ev || typeof ev.kind !== "string") return;
    setLiveStatus((prev) => {
      if (!prev) return prev;
      const e = ev.payload as Partial<RunEvent> | undefined;
      if (!e) return prev;
      try {
        return runOverviewReducer(prev, { kind: ev.kind, ...(e as object) } as RunEvent);
      } catch {
        return prev;
      }
    });
  }, []);

  // subscribe to /ws/run/<runId> when known; using a stable channel string
  const wsChannel = runId ? `/ws/run/${runId}` : "/ws/run/_pending";
  // Subscribe only if runId known; conditional subscribe via early-return inside hook is unsafe → use noop channel
  useWs(runId ? wsChannel : "/ws/run/_idle", onWsEvent);

  const handlePause = async (): Promise<void> => {
    if (!runId) return;
    setControlError(null);
    try {
      const next = await pauseRun(runId);
      setLiveStatus(next);
    } catch (e) {
      const err = e as RunControlError;
      setControlError({ code: err.code ?? "BAD_REQUEST", message: err.message ?? "" });
    }
  };

  const handleCancel = async (): Promise<void> => {
    if (!runId) return;
    setControlError(null);
    try {
      const next = await cancelRun(runId);
      setLiveStatus(next);
    } catch (e) {
      const err = e as RunControlError;
      setControlError({ code: err.code ?? "BAD_REQUEST", message: err.message ?? "" });
    }
  };

  if (runQ.isLoading) {
    return (
      <div data-testid="run-overview-loading" style={{ padding: 24, color: "var(--fg-mute)" }}>
        加载中…
      </div>
    );
  }

  if (!liveStatus) {
    return (
      <div
        data-testid="run-overview-empty"
        style={{
          padding: 64,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          color: "var(--fg-dim)",
        }}
      >
        <div style={{ fontSize: 32, marginBottom: 12 }}>🌙</div>
        <div style={{ fontSize: 16, fontWeight: 500 }}>
          {currentWorkdir ? "无运行中的 run" : "请先选择工作目录"}
        </div>
        {currentWorkdir && (
          <div
            data-testid="run-overview-current-workdir"
            style={{
              marginTop: 8,
              fontSize: 11,
              color: "var(--fg-mute)",
              fontFamily: "var(--font-mono)",
            }}
          >
            {currentWorkdir}
          </div>
        )}
        <button
          data-testid="btn-start-run"
          type="button"
          onClick={() => {
            void handleStart();
          }}
          disabled={startRun.isPending || selectWorkdirMut.isPending}
          aria-busy={startRun.isPending ? "true" : "false"}
          style={{
            marginTop: 24,
            padding: "8px 16px",
            borderRadius: 6,
            background: "var(--accent)",
            color: "var(--fg-on-accent)",
            fontSize: 13,
            fontWeight: 600,
            border: "none",
            cursor: startRun.isPending ? "wait" : "pointer",
            opacity: startRun.isPending ? 0.6 : 1,
          }}
        >
          {startRun.isPending
            ? "Starting…"
            : currentWorkdir
              ? "Start"
              : "选择工作目录"}
        </button>
        {controlError && (
          <div
            data-testid="run-start-error-toast"
            role="alert"
            data-error="true"
            style={{
              marginTop: 12,
              padding: "8px 12px",
              borderRadius: 6,
              background: "rgba(255,107,107,0.12)",
              color: "var(--state-fail)",
              fontSize: 12,
            }}
          >
            {controlError.code}: {controlError.message}
          </div>
        )}
      </div>
    );
  }

  const phaseIdx = liveStatus.current_phase ? PHASE_INDEX[liveStatus.current_phase] ?? 0 : 0;
  const subprogressFraction =
    liveStatus.subprogress != null
      ? `${liveStatus.subprogress.n}/${liveStatus.subprogress.m}`
      : undefined;
  const phaseLabel = liveStatus.current_phase ?? "—";
  const workLabel =
    liveStatus.current_phase === "work" && liveStatus.subprogress
      ? `work ${liveStatus.subprogress.n}/${liveStatus.subprogress.m}`
      : phaseLabel;

  return (
    <div data-component="run-overview-page" style={{ padding: 24 }}>
      <header
        data-testid="run-state-header"
        style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}
      >
        <span
          data-testid="run-state-chip"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "2px 10px",
            borderRadius: 999,
            background: "var(--bg-active)",
            fontSize: 11.5,
          }}
        >
          <span
            className="state-dot pulse"
            data-state={liveStatus.state}
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background:
                liveStatus.state === "running"
                  ? "var(--state-running)"
                  : liveStatus.state === "paused"
                    ? "var(--state-hil)"
                    : liveStatus.state === "failed"
                      ? "var(--state-fail)"
                      : "var(--fg-mute)",
            }}
          />
          {liveStatus.state}
        </span>
        <span data-testid="phase-label" style={{ fontSize: 13, color: "var(--fg-dim)" }}>
          {workLabel}
        </span>
      </header>

      <PhaseStepper current={phaseIdx} fraction={subprogressFraction} />

      <div
        data-testid="metrics-card"
        style={{
          marginTop: 24,
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 12,
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: 8,
          padding: 16,
        }}
      >
        <div data-row="cost" data-testid="run-cost">
          <div style={{ fontSize: 11, color: "var(--fg-mute)" }}>
            <Icons.DollarSign size={12} /> cost_usd
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, fontFamily: "var(--font-mono)" }}>
            ${(liveStatus.cost_usd ?? 0).toFixed(2)}
          </div>
        </div>
        <div data-row="turns" data-testid="run-turns">
          <div style={{ fontSize: 11, color: "var(--fg-mute)" }}>
            <Icons.RefreshCw size={12} /> num_turns
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, fontFamily: "var(--font-mono)" }}>
            {liveStatus.num_turns ?? 0}
          </div>
        </div>
        <div data-row="head" data-testid="run-head">
          <div style={{ fontSize: 11, color: "var(--fg-mute)" }}>
            <Icons.GitCommit size={12} /> head
          </div>
          <div style={{ fontSize: 13, fontFamily: "var(--font-mono)" }}>
            {liveStatus.head_latest ?? "—"}
          </div>
        </div>
        <div data-row="skill" data-testid="current-skill">
          <div style={{ fontSize: 11, color: "var(--fg-mute)" }}>
            <Icons.Cpu size={12} /> skill
          </div>
          <div style={{ fontSize: 13 }}>{liveStatus.current_skill ?? "—"}</div>
        </div>
        <div data-row="feature" data-testid="current-feature">
          <div style={{ fontSize: 11, color: "var(--fg-mute)" }}>
            <Icons.Book size={12} /> feature
          </div>
          <div style={{ fontSize: 13 }}>
            {liveStatus.current_feature
              ? `#${liveStatus.current_feature.id} ${liveStatus.current_feature.title}`
              : "—"}
          </div>
        </div>
        <div data-row="duration">
          <div style={{ fontSize: 11, color: "var(--fg-mute)" }}>
            <Icons.Clock size={12} /> started_at
          </div>
          <div style={{ fontSize: 12, fontFamily: "var(--font-mono)" }}>
            {liveStatus.started_at ?? "—"}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <button
          data-testid="btn-pause"
          type="button"
          onClick={handlePause}
          disabled={liveStatus.state !== "running" && liveStatus.state !== "paused"}
          style={{
            padding: "6px 12px",
            borderRadius: 6,
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            color: "var(--fg)",
            fontSize: 13,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Icons.Pause size={13} /> 暂停
        </button>
        <button
          data-testid="btn-cancel"
          type="button"
          onClick={handleCancel}
          style={{
            padding: "6px 12px",
            borderRadius: 6,
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            color: "var(--state-fail)",
            fontSize: 13,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Icons.X size={13} /> 取消
        </button>
        {controlError && (
          <span
            data-testid="run-control-error"
            style={{
              marginLeft: "auto",
              padding: "4px 10px",
              borderRadius: 6,
              background: "rgba(255,107,107,0.12)",
              color: "var(--state-fail)",
              fontSize: 12,
            }}
          >
            {controlError.code}: {controlError.message}
          </span>
        )}
      </div>
    </div>
  );
}
