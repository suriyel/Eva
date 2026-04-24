/**
 * PhaseStepper — 8-phase horizontal stepper with done/current/pending states.
 * Traces §VRC PhaseStepper · §BC current range [0,7] · §"Visual Rendering Contract" pulse rule.
 */
import * as React from "react";
import { Icons } from "./icons";

type PhaseState = "done" | "current" | "pending";

interface Phase {
  id: string;
  label: string;
  color: string;
}

const PHASES: Phase[] = [
  { id: "req", label: "需求", color: "var(--phase-req)" },
  { id: "ucd", label: "UCD", color: "var(--phase-ucd)" },
  { id: "design", label: "设计", color: "var(--phase-design)" },
  { id: "ats", label: "ATS", color: "var(--phase-ats)" },
  { id: "init", label: "初始化", color: "var(--phase-init)" },
  { id: "work", label: "开发", color: "var(--phase-work)" },
  { id: "st", label: "系统测试", color: "var(--phase-st)" },
  { id: "finalize", label: "归档", color: "var(--phase-finalize)" },
];

export interface PhaseStepperProps {
  current: number;
  fraction?: string;
  variant?: "h" | "v";
}

// Sync-read on every render covers tests that stub matchMedia pre-render; the
// effect keeps it live-updating when the user toggles the OS setting.
// Duplicated in ticket-card.tsx — two copies is cheaper than a cross-component hook
// export while the rule set stays this small.
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = React.useState(false);
  React.useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const handler = (ev: MediaQueryListEvent): void => setReduced(ev.matches);
    mq.addEventListener?.("change", handler);
    return () => mq.removeEventListener?.("change", handler);
  }, []);
  if (typeof window !== "undefined" && window.matchMedia) {
    try {
      const synchronous = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (synchronous !== reduced) return synchronous;
    } catch {
      /* ignore */
    }
  }
  return reduced;
}

export function PhaseStepper({ current, fraction, variant = "h" }: PhaseStepperProps): React.ReactElement {
  if (!Number.isInteger(current) || current < 0 || current > 7) {
    throw new RangeError(`PhaseStepper.current must be integer in [0,7] (got ${current})`);
  }
  const reduced = usePrefersReducedMotion();
  const direction = variant === "v" ? "column" : "row";

  return (
    <div
      data-component="phase-stepper"
      style={{ display: "flex", flexDirection: direction, alignItems: "flex-start", gap: 0, padding: "8px 4px" }}
    >
      {PHASES.map((p, i) => {
        const state: PhaseState = i < current ? "done" : i === current ? "current" : "pending";
        return (
          <React.Fragment key={p.id}>
            <div
              data-phase-index={i}
              data-state={state}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 8,
                flex: "none",
                width: 84,
              }}
            >
              <div
                style={{
                  position: "relative",
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: state === "pending" ? "transparent" : p.color,
                  border: state === "pending" ? "1.5px solid var(--border)" : "none",
                  display: "grid",
                  placeItems: "center",
                  boxShadow: state === "current" ? `0 0 0 4px ${p.color}22` : "none",
                  transition: "all 180ms",
                }}
              >
                {state === "done" && <Icons.Check size={14} style={{ color: "#0A0D12" }} />}
                {state === "current" && (
                  <>
                    <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#0A0D12" }} />
                    <div
                      data-pulse=""
                      style={{
                        position: "absolute",
                        inset: -6,
                        borderRadius: "50%",
                        border: `1.5px solid ${p.color}`,
                        animationName: reduced ? "none" : "hns-pulse",
                        animationDuration: "1.8s",
                        animationTimingFunction: "ease-out",
                        animationIterationCount: "infinite",
                      }}
                    />
                  </>
                )}
                {state === "pending" && (
                  <div style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--fg-faint)" }} />
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: state === "current" ? 600 : 500,
                    color: state === "pending" ? "var(--fg-mute)" : "var(--fg)",
                  }}
                >
                  {p.label}
                </div>
                {i === current && fraction && (
                  <div className="mono" style={{ fontSize: 10.5, color: p.color }}>
                    {fraction}
                  </div>
                )}
              </div>
            </div>
            {i < PHASES.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  marginTop: 15,
                  background: i < current ? p.color : "var(--border-subtle)",
                  borderRadius: 1,
                  opacity: i < current ? 0.6 : 1,
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
