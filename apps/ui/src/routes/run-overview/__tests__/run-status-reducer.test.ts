/**
 * runOverviewReducer —— RunStatus 累加 reducer 纯函数测试
 *
 * Traces To 特性 21 design §Interface Contract `runOverviewReducer` ·
 *           §Test Inventory T01（cost 累加）/ T02（subprogress）/ T29（phase 转移）·
 *           SRS FR-030 AC-1（cost = Σ ticket.cost_usd）+ AC-2（work N/M）。
 *
 * Red 阶段：`run-status-reducer.ts` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「reducer 直接 mutate 入参」→ T29 immutable 断言 FAIL
 *   - 「漏 RunPhaseChanged」→ T29 phase 仍是旧值 FAIL
 *   - 「cost 字段被覆盖而非累加」→ T01 sum 断言 FAIL
 *
 * [unit] —— pure-function tests, no integration required for this file.
 */
import { describe, it, expect } from "vitest";
import {
  runOverviewReducer,
  type RunStatus,
  type RunEvent,
} from "@/routes/run-overview/run-status-reducer";

function baseStatus(overrides: Partial<RunStatus> = {}): RunStatus {
  return {
    run_id: "r-1",
    state: "running",
    current_phase: "requirements",
    cost_usd: 0,
    num_turns: 0,
    head_latest: null,
    started_at: "2026-04-25T08:00:00Z",
    ended_at: null,
    current_skill: null,
    current_feature: null,
    subprogress: null,
    ...overrides,
  };
}

describe("runOverviewReducer 纯函数累加 (FR-030)", () => {
  it("T01 累加 3 条 TicketStateChanged.cost_usd=0.05 后 cost_usd=0.15", () => {
    const initial = baseStatus({ cost_usd: 0 });
    const ev1: RunEvent = {
      kind: "ticket_state_changed",
      ticket_id: "t-1",
      cost_usd: 0.05,
      num_turns: 1,
    };
    const ev2: RunEvent = { ...ev1, ticket_id: "t-2" };
    const ev3: RunEvent = { ...ev1, ticket_id: "t-3" };
    let s = runOverviewReducer(initial, ev1);
    s = runOverviewReducer(s, ev2);
    s = runOverviewReducer(s, ev3);
    // 浮点累加用近似断言（容差 1e-9 防 FP 漂移）
    expect(s.cost_usd).toBeCloseTo(0.15, 9);
    expect(s.num_turns).toBe(3);
  });

  it("T02 RunPhaseChanged 含 subprogress {n:3,m:8} → state.subprogress 同步且不丢", () => {
    const initial = baseStatus({ current_phase: "design", subprogress: null });
    const ev: RunEvent = {
      kind: "run_phase_changed",
      phase: "work",
      subprogress: { n: 3, m: 8 },
    };
    const next = runOverviewReducer(initial, ev);
    expect(next.current_phase).toBe("work");
    expect(next.subprogress).toEqual({ n: 3, m: 8 });
  });

  it("T29 immutable —— reducer 不 mutate 入参 state（旧引用 cost 不变）", () => {
    const initial = baseStatus({ cost_usd: 0.1 });
    const snapshot = { ...initial };
    runOverviewReducer(initial, {
      kind: "ticket_state_changed",
      ticket_id: "t-1",
      cost_usd: 0.05,
      num_turns: 1,
    });
    expect(initial).toEqual(snapshot);
    // 引用恒等：reducer 必须返回新对象
    const next = runOverviewReducer(initial, {
      kind: "run_phase_changed",
      phase: "design",
    });
    expect(next).not.toBe(initial);
  });

  it("T29b RunCompleted → state='completed' 且 ended_at 落定（非空字符串）", () => {
    const initial = baseStatus({ state: "running", ended_at: null });
    const next = runOverviewReducer(initial, {
      kind: "run_completed",
      ended_at: "2026-04-25T09:00:00Z",
    });
    expect(next.state).toBe("completed");
    expect(next.ended_at).toBe("2026-04-25T09:00:00Z");
  });

  it("FUNC/error —— 非法 schema 输入应被 zod 守卫抛 TypeError（Raises 列）", () => {
    const initial = baseStatus();
    expect(() =>
      runOverviewReducer(initial, { kind: "ticket_state_changed" } as unknown as RunEvent),
    ).toThrow();
  });

  it("BNDRY/edge —— 未知 kind 不修改 state（容错）", () => {
    const initial = baseStatus({ cost_usd: 0.5 });
    const next = runOverviewReducer(initial, { kind: "unknown_event" } as unknown as RunEvent);
    expect(next.cost_usd).toBe(0.5);
    expect(next.current_phase).toBe(initial.current_phase);
  });

  it("FUNC/error —— state 不是 RunStatus 对象（null）抛 TypeError（FR-030 守卫）", () => {
    expect(() =>
      runOverviewReducer(null as unknown as RunStatus, {
        kind: "run_phase_changed",
        phase: "design",
      }),
    ).toThrow(TypeError);
  });

  it("BNDRY/edge —— ev 不是对象（null）→ 返回原 state 引用（容错路径）", () => {
    const initial = baseStatus({ cost_usd: 0.5 });
    const next = runOverviewReducer(initial, null as unknown as RunEvent);
    expect(next).toBe(initial);
  });

  it("BNDRY/edge —— ev.kind 不是 string → 返回原 state 引用", () => {
    const initial = baseStatus({ cost_usd: 0.5 });
    const next = runOverviewReducer(initial, { kind: 123 } as unknown as RunEvent);
    expect(next).toBe(initial);
  });

  it("FUNC/error —— run_phase_changed.phase 非 string → 抛 TypeError（行 99-100）", () => {
    const initial = baseStatus();
    expect(() =>
      runOverviewReducer(initial, {
        kind: "run_phase_changed",
        phase: 7,
      } as unknown as RunEvent),
    ).toThrow(TypeError);
  });

  it("FUNC/error —— run_completed.ended_at 非 string → 抛 TypeError（行 110-111）", () => {
    const initial = baseStatus();
    expect(() =>
      runOverviewReducer(initial, {
        kind: "run_completed",
        ended_at: 0,
      } as unknown as RunEvent),
    ).toThrow(TypeError);
  });

  it("T02b run_phase_changed 不带 subprogress → 默认置 null（?? 分支）", () => {
    const initial = baseStatus({ subprogress: { n: 1, m: 2 } });
    const next = runOverviewReducer(initial, {
      kind: "run_phase_changed",
      phase: "ats",
    });
    expect(next.subprogress).toBeNull();
    expect(next.current_phase).toBe("ats");
  });
});
