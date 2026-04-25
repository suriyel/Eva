/**
 * deriveHilControl —— FR-010 4 AC × multi_select × options × allow_freeform 派生表
 *
 * Traces To 特性 21 design §Interface Contract `deriveHilControl` ·
 *           §Implementation Summary flowchart TD（4 决策菱形 + 1 错误终点）·
 *           §Test Inventory T05 / T06 / T07 / T08 / T09 / T10 / T11 ·
 *           SRS FR-010 AC-1..4 + NFR-011（派生 + 视觉标注）。
 *
 * Red 阶段：模块 `derive-control.ts` 尚未实现，所有用例必须 ImportError / TypeError
 * 形态 FAIL；Green 阶段实现 5-类返回 + 1-类抛错。
 *
 * Rule 4 错误实现挑战：
 *   - 「全部返回 'radio'」→ T06/T07/T10/T11 FAIL
 *   - 「忽略 allow_freeform」→ T08/T09 FAIL
 *   - 「options==[] 静默渲染空 list」→ T10 FAIL（要求显式抛错而非静默）
 *
 * [unit] —— pure-function tests, no I/O, no integration test required for this file.
 */
import { describe, it, expect } from "vitest";
import {
  deriveHilControl,
  InvalidHilQuestionError,
  type HilQuestionLike,
} from "@/routes/hil-inbox/derive-control";

function q(partial: Partial<HilQuestionLike>): HilQuestionLike {
  return {
    multi_select: false,
    options: [],
    allow_freeform: false,
    ...partial,
  };
}

describe("deriveHilControl 派生 (FR-010 / flowchart TD)", () => {
  it("T05 multi_select=false + options.length=2 + allow_freeform=false → 'radio' (AC-1)", () => {
    expect(
      deriveHilControl(
        q({ multi_select: false, options: [{ label: "A" }, { label: "B" }], allow_freeform: false }),
      ),
    ).toBe("radio");
  });

  it("T06 multi_select=true + options.length=3 + allow_freeform=false → 'checkbox' (AC-2)", () => {
    expect(
      deriveHilControl(
        q({
          multi_select: true,
          options: [{ label: "A" }, { label: "B" }, { label: "C" }],
          allow_freeform: false,
        }),
      ),
    ).toBe("checkbox");
  });

  it("T07 multi_select=false + options=[] + allow_freeform=true → 'textarea' (AC-3)", () => {
    expect(
      deriveHilControl(q({ multi_select: false, options: [], allow_freeform: true })),
    ).toBe("textarea");
  });

  it("T08 multi_select=false + options.length=2 + allow_freeform=true → 'radio_with_freeform' (AC-4)", () => {
    expect(
      deriveHilControl(
        q({ multi_select: false, options: [{ label: "A" }, { label: "B" }], allow_freeform: true }),
      ),
    ).toBe("radio_with_freeform");
  });

  it("T09 multi_select=true + options.length=2 + allow_freeform=true → 'checkbox_with_freeform' (AC-4 multi 变体)", () => {
    expect(
      deriveHilControl(
        q({ multi_select: true, options: [{ label: "A" }, { label: "B" }], allow_freeform: true }),
      ),
    ).toBe("checkbox_with_freeform");
  });

  it("T10 multi_select=false + options=[] + allow_freeform=false → 抛 InvalidHilQuestionError (Raises)", () => {
    expect(() =>
      deriveHilControl(q({ multi_select: false, options: [], allow_freeform: false })),
    ).toThrow(InvalidHilQuestionError);
  });

  it("T11 BNDRY/edge —— options.length=1 单选项也合法 → 'radio'（off-by-one 防御）", () => {
    expect(
      deriveHilControl(q({ multi_select: false, options: [{ label: "Only" }], allow_freeform: false })),
    ).toBe("radio");
  });

  it("T11b BNDRY/edge —— options.length=1 + allow_freeform=true → 'radio_with_freeform'", () => {
    expect(
      deriveHilControl(q({ multi_select: false, options: [{ label: "Only" }], allow_freeform: true })),
    ).toBe("radio_with_freeform");
  });

  it("T10b FUNC/error —— multi_select=true + options=[] + allow_freeform=false → 抛 InvalidHilQuestionError", () => {
    expect(() =>
      deriveHilControl(q({ multi_select: true, options: [], allow_freeform: false })),
    ).toThrow(InvalidHilQuestionError);
  });

  it("Rule 4 错误实现挑战 —— InvalidHilQuestionError 必须是 Error 子类（catch 链 instanceof 通过）", () => {
    try {
      deriveHilControl(q({ multi_select: false, options: [], allow_freeform: false }));
    } catch (e) {
      expect(e).toBeInstanceOf(Error);
      expect(e).toBeInstanceOf(InvalidHilQuestionError);
      expect((e as Error).name).toBe("InvalidHilQuestionError");
      return;
    }
    throw new Error("expected throw, got nothing");
  });
});
