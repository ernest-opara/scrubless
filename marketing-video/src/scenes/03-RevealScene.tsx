import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Eyebrow } from "../components/Eyebrow";
import { theme } from "../theme";

/**
 * Scene 3 (0:08-0:14) — the landing page fades up from black. Stylised
 * rebuild of the Scrubless landing's hero so the timing's deterministic
 * and the layout always reads. Cursor enters on the right beat.
 */
export const RevealScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 0..15: fade from black to cream. After: stable hero.
  const fadeFromBlack = interpolate(frame, [0, 18], [0, 1], {
    extrapolateRight: "clamp",
  });

  const titleSpring = spring({
    fps,
    frame: frame - 14,
    config: { damping: 22, mass: 0.7 },
  });

  return (
    <AbsoluteFill style={{ background: theme.bg }}>
      {/* black-out layer that fades to transparent over the first 18 frames */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "#000",
          opacity: 1 - fadeFromBlack,
        }}
      />

      <div
        style={{
          padding: "92px 140px",
          opacity: fadeFromBlack,
          transform: `translateY(${interpolate(titleSpring, [0, 1], [16, 0])}px)`,
        }}
      >
        <Eyebrow>Semantic Video Search</Eyebrow>
        <h1
          style={{
            fontFamily: theme.fontDisplay,
            fontWeight: 400,
            fontSize: 168,
            lineHeight: 0.98,
            letterSpacing: "-0.012em",
            margin: "32px 0 0",
            color: theme.fg,
          }}
        >
          Stop scrubbing.
          <br />
          Start{" "}
          <em style={{ fontStyle: "italic", color: theme.accent }}>
            searching.
          </em>
        </h1>
      </div>
    </AbsoluteFill>
  );
};
