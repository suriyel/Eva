/**
 * RoiDisabledButton — F22 §IC Section C.
 * FR-035b/036/037 are Won't (v1) → button is disabled and exposes a tooltip
 * "v1.1 规划中" on hover. onClick never triggers any mutation/query.
 */
import * as React from "react";

export interface RoiDisabledButtonProps {
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
}

export function RoiDisabledButton(
  props: RoiDisabledButtonProps,
): React.ReactElement {
  const [hover, setHover] = React.useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <button
        type="button"
        data-testid="roi-button"
        disabled
        aria-disabled="true"
        // Note: native disabled prevents onClick anyway; we still pass props.onClick
        // through so spies can confirm it isn't invoked when the user clicks.
        onClick={(e) => {
          // Do nothing — defence in depth even if a parent removes disabled.
          e.preventDefault();
          // Intentionally do NOT call props.onClick — onClick must NOT fire any
          // mutation/query (per design §IC RoiDisabledButton).
          if (props.onClick) {
            // Discard — we keep the prop only for parent compose ergonomics.
          }
        }}
      >
        ROI 分析
      </button>
      {hover && (
        <span data-testid="roi-tooltip" role="tooltip">
          v1.1 规划中
        </span>
      )}
    </span>
  );
}
