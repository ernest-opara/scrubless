import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Eyebrow } from "../components/Eyebrow";
import { theme } from "../theme";

/**
 * Scene 6 (0:34-0:44) — Ask with citations. As with scenes 4-5, swap to a
 * real screen recording (public/demo-ask.mp4) when you have it.
 */
const USE_REAL_RECORDING = false;

export const DemoAskScene: React.FC = () => {
  const frame = useCurrentFrame();

  if (USE_REAL_RECORDING) {
    return (
      <AbsoluteFill style={{ background: theme.bg }}>
        <OffthreadVideo
          src={staticFile("demo-ask.mp4")}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill
      style={{
        background: theme.bg,
        padding: "0 8%",
        alignItems: "center",
        justifyContent: "center",
        gap: 32,
      }}
    >
      <Eyebrow>Ask · cited</Eyebrow>
      <h2
        style={{
          fontFamily: theme.fontDisplay,
          fontWeight: 400,
          fontSize: 108,
          lineHeight: 1.05,
          textAlign: "center",
          margin: 0,
          color: theme.fg,
        }}
      >
        Ask a question.{" "}
        <em style={{ color: theme.accent }}>Get the second.</em>
      </h2>

      {/* Stand-in citation answer card */}
      <div
        style={{
          background: theme.bgCard,
          border: `1px solid ${theme.line}`,
          borderRadius: 14,
          padding: "28px 32px",
          maxWidth: 1100,
          fontFamily: theme.fontBody,
          fontSize: 26,
          color: theme.fg,
          lineHeight: 1.45,
          opacity: Math.min(1, frame / 36),
        }}
      >
        They decided to push the launch to Q3 on{" "}
        <span style={{ color: theme.accent, textDecoration: "underline" }}>
          [Episode 04 @ 23:01]
        </span>
        , citing the customer interviews from week two.
      </div>

      <p
        style={{
          fontFamily: theme.fontMono,
          color: theme.fgFaint,
          fontSize: 16,
          marginTop: 24,
          opacity: Math.max(0, 1 - frame / 60),
        }}
      >
        TODO · drop a real recording into public/demo-ask.mp4
      </p>
    </AbsoluteFill>
  );
};
