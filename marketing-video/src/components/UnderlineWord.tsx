import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { theme } from "../theme";

interface Props {
  children: React.ReactNode;
  /** Frame the underline should start drawing. Default 0. */
  start?: number;
  /** Color of the underline. Defaults to the indigo accent. */
  color?: string;
  /** Thickness of the underline in px. Default 8. */
  thickness?: number;
}

/**
 * Inline-flow word with an animated indigo underline. Drives the brand-level
 * "underline the word that matters" gesture — see scenes 08 and 09.
 */
export const UnderlineWord: React.FC<Props> = ({
  children,
  start = 0,
  color = theme.accent,
  thickness = 8,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = Math.max(0, frame - start);
  const draw = spring({
    fps,
    frame: localFrame,
    config: { damping: 18, stiffness: 90, mass: 0.6 },
  });
  const width = interpolate(draw, [0, 1], [0, 100], {
    extrapolateRight: "clamp",
  });
  return (
    <span style={{ position: "relative", display: "inline-block" }}>
      {children}
      <span
        style={{
          position: "absolute",
          left: 0,
          bottom: "-0.08em",
          height: thickness,
          width: `${width}%`,
          background: color,
          borderRadius: thickness,
        }}
      />
    </span>
  );
};
