/**
 * runOverviewReducer —— RunStatus 累加 reducer
 *
 * Traces §Interface Contract `runOverviewReducer` postcondition ·
 *        SRS FR-030 AC-1（cost = Σ ticket.cost_usd）+ AC-2（subprogress N/M）。
 *
 * 纯函数：返回新对象，禁止 mutation。
 *
 * 支持的事件：
 *   - ticket_state_changed { ticket_id, cost_usd, num_turns } → 累加到 RunStatus
 *   - run_phase_changed     { phase, subprogress? }           → 更新 current_phase
 *   - run_completed         { ended_at }                      → state="completed", ended_at
 *
 * 未知 kind：返回 state 引用（容错；BNDRY/edge）。
 * 非法 schema（缺关键字段）：抛 TypeError。
 */

export type RunPhase =
  | "requirements"
  | "ucd"
  | "design"
  | "ats"
  | "init"
  | "work"
  | "st"
  | "finalize";

export type RunState = "running" | "paused" | "completed" | "cancelled" | "failed";

export interface RunSubprogress {
  n: number;
  m: number;
}

export interface RunCurrentFeature {
  id: number;
  title: string;
}

export interface RunStatus {
  run_id: string;
  state: RunState;
  current_phase: RunPhase | null;
  cost_usd: number;
  num_turns: number;
  head_latest: string | null;
  started_at: string | null;
  ended_at: string | null;
  current_skill: string | null;
  current_feature: RunCurrentFeature | null;
  subprogress: RunSubprogress | null;
}

export type RunEvent =
  | {
      kind: "ticket_state_changed";
      ticket_id: string;
      cost_usd: number;
      num_turns: number;
    }
  | {
      kind: "run_phase_changed";
      phase: RunPhase;
      subprogress?: RunSubprogress | null;
    }
  | { kind: "run_completed"; ended_at: string }
  | { kind: "ticket_spawned"; ticket_id: string }
  | { kind: string };

function isObj(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object";
}

export function runOverviewReducer(state: RunStatus, ev: RunEvent): RunStatus {
  if (!isObj(state)) {
    throw new TypeError("runOverviewReducer: state must be a RunStatus object");
  }
  if (!isObj(ev) || typeof (ev as Record<string, unknown>).kind !== "string") {
    return state;
  }

  switch (ev.kind) {
    case "ticket_state_changed": {
      const e = ev as Extract<RunEvent, { kind: "ticket_state_changed" }>;
      if (typeof e.cost_usd !== "number" || typeof e.num_turns !== "number") {
        throw new TypeError(
          "ticket_state_changed: cost_usd & num_turns must be numbers",
        );
      }
      return {
        ...state,
        cost_usd: state.cost_usd + e.cost_usd,
        num_turns: state.num_turns + e.num_turns,
      };
    }
    case "run_phase_changed": {
      const e = ev as Extract<RunEvent, { kind: "run_phase_changed" }>;
      if (typeof e.phase !== "string") {
        throw new TypeError("run_phase_changed: phase must be a string");
      }
      return {
        ...state,
        current_phase: e.phase,
        subprogress: e.subprogress ?? null,
      };
    }
    case "run_completed": {
      const e = ev as Extract<RunEvent, { kind: "run_completed" }>;
      if (typeof e.ended_at !== "string") {
        throw new TypeError("run_completed: ended_at must be a string");
      }
      return { ...state, state: "completed", ended_at: e.ended_at };
    }
    default:
      // unknown kind → return same reference
      return state;
  }
}
