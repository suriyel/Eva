/**
 * deriveHilControl —— 纯函数：HilQuestion → 控件类型
 *
 * Traces §Interface Contract `deriveHilControl` ·
 *        §Implementation Summary flowchart TD ·
 *        SRS FR-010 AC-1..4 + NFR-011。
 *
 * 决策分支严格对齐 §Implementation Summary flowchart TD：
 *   1. multi_select=true && allow_freeform && options.length>0  → checkbox_with_freeform
 *   2. multi_select=true                                        → checkbox（含 options=[] 的 InvalidHilQuestionError）
 *   3. allow_freeform && options.length==0                       → textarea
 *   4. options.length>=1 && !allow_freeform                      → radio
 *   5. options.length>=1 && allow_freeform                       → radio_with_freeform
 *   6. otherwise                                                 → throw InvalidHilQuestionError
 */

export interface HilOptionLike {
  label: string;
  desc?: string;
}

export interface HilQuestionLike {
  multi_select: boolean;
  options: HilOptionLike[];
  allow_freeform: boolean;
}

export type HilControlVariant =
  | "radio"
  | "checkbox"
  | "textarea"
  | "radio_with_freeform"
  | "checkbox_with_freeform";

export class InvalidHilQuestionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InvalidHilQuestionError";
    Object.setPrototypeOf(this, InvalidHilQuestionError.prototype);
  }
}

export function deriveHilControl(q: HilQuestionLike): HilControlVariant {
  const optsLen = Array.isArray(q.options) ? q.options.length : 0;

  // Branch 1: multi_select=true
  if (q.multi_select === true) {
    if (q.allow_freeform === true && optsLen > 0) return "checkbox_with_freeform";
    if (optsLen === 0) {
      throw new InvalidHilQuestionError(
        "multi_select=true 但 options 为空且 allow_freeform=false——无可渲染控件",
      );
    }
    return "checkbox";
  }

  // Branch 2: multi_select=false, options=[], allow_freeform=true → textarea
  if (q.allow_freeform === true && optsLen === 0) {
    return "textarea";
  }

  // Branch 3: multi_select=false, options.length>=1, allow_freeform=false → radio
  if (optsLen >= 1 && q.allow_freeform !== true) {
    return "radio";
  }

  // Branch 4: multi_select=false, options.length>=1, allow_freeform=true → radio_with_freeform
  if (optsLen >= 1 && q.allow_freeform === true) {
    return "radio_with_freeform";
  }

  // Otherwise: options=[] && !allow_freeform → 抛错（FR-010 隐含约束）
  throw new InvalidHilQuestionError(
    "无可渲染控件：options 为空且 allow_freeform=false",
  );
}
