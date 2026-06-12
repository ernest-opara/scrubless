import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { UnderlineWord } from "../components/UnderlineWord";
import { theme } from "../theme";

/**
 * Scene 8 (0:52-1:00) — the magic line. Full-bleed cream. Two sentences,
 * "Search what was said. Search what was shown." Underlines draw on "said"
 * and "shown" on different beats — that's the brand gesture.
 */
export const HeadlineScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 14], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: theme.bg,
        alignItems: "center",
        justifyContent: "center",
        padding: "0 8%",
        opacity,
      }}
    >
      <h2
        style={{
          fontFamily: theme.fontDisplay,
          fontWeight: 400,
          fontSize: 124,
          lineHeight: 1.06,
          letterSpacing: "-0.012em",
          margin: 0,
          textAlign: "center",
          color: theme.fg,
        }}
      >
        <span style={{ display: "block", marginBottom: 28 }}>
          Search what was{" "}
          <UnderlineWord start={40} thickness={10}>
            said.
          </UnderlineWord>
        </span>
        <span style={{ display: "block" }}>
          Search what was{" "}
          <UnderlineWord start={120} thickness={10}>
            shown.
          </UnderlineWord>
        </span>
      </h2>
    </AbsoluteFill>
  );
};
