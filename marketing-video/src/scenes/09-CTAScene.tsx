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
 * Scene 9 (1:00-1:08) — the CTA. Brand line, dark pill button, URL. The
 * pill button does a tiny spring entrance to draw the eye after the
 * headline scene resolves.
 */
export const CTAScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({
    fps,
    frame,
    config: { damping: 20, mass: 0.7, stiffness: 90 },
  });
  const pillEnter = spring({
    fps,
    frame: frame - 18,
    config: { damping: 16, mass: 0.5, stiffness: 110 },
  });

  return (
    <AbsoluteFill
      style={{
        background: theme.bg,
        alignItems: "center",
        justifyContent: "center",
        padding: "0 8%",
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [12, 0])}px)`,
      }}
    >
      <Eyebrow>Try it free</Eyebrow>

      <h2
        style={{
          fontFamily: theme.fontDisplay,
          fontWeight: 400,
          fontSize: 152,
          lineHeight: 1.0,
          letterSpacing: "-0.012em",
          margin: "32px 0 12px",
          textAlign: "center",
          color: theme.fg,
        }}
      >
        Stop scrubbing. <br />
        Start{" "}
        <em style={{ fontStyle: "italic", color: theme.accent }}>
          searching.
        </em>
      </h2>

      <div
        style={{
          marginTop: 40,
          padding: "22px 56px",
          background: theme.bgDark,
          color: theme.fgInverse,
          borderRadius: 999,
          fontFamily: theme.fontBody,
          fontSize: 28,
          fontWeight: 500,
          letterSpacing: "0.005em",
          transform: `translateY(${interpolate(pillEnter, [0, 1], [12, 0])}px) scale(${interpolate(pillEnter, [0, 1], [0.96, 1])})`,
          opacity: pillEnter,
          boxShadow: theme.shadowMd,
        }}
      >
        getscrubless.com&nbsp;&nbsp;→
      </div>
    </AbsoluteFill>
  );
};
