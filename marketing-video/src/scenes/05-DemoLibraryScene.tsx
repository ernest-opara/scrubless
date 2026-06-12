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
 * Scene 5 (0:24-0:34) — folder search. Same swap pattern as scene 4: drop a
 * real recording into public/demo-library.mp4 and flip USE_REAL_RECORDING to
 * true. Until then we render a copy-led title card so the pacing still works.
 */
const USE_REAL_RECORDING = false;

export const DemoLibraryScene: React.FC = () => {
  const frame = useCurrentFrame();

  if (USE_REAL_RECORDING) {
    return (
      <AbsoluteFill style={{ background: theme.bg }}>
        <OffthreadVideo
          src={staticFile("demo-library.mp4")}
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
        gap: 36,
      }}
    >
      <Eyebrow>Across a whole folder</Eyebrow>
      <h2
        style={{
          fontFamily: theme.fontDisplay,
          fontWeight: 400,
          fontSize: 116,
          lineHeight: 1.05,
          textAlign: "center",
          margin: 0,
          color: theme.fg,
        }}
      >
        One query.{" "}
        <em style={{ color: theme.accent }}>Every clip.</em>
      </h2>
      <p
        style={{
          color: theme.fgMuted,
          fontSize: 28,
          maxWidth: 900,
          textAlign: "center",
          margin: 0,
        }}
      >
        Drop in a directory of videos. Scrubless indexes the lot, then jumps
        you to the exact moment across every file.
      </p>
      <p
        style={{
          fontFamily: theme.fontMono,
          color: theme.fgFaint,
          fontSize: 16,
          marginTop: 24,
          opacity: Math.max(0, 1 - frame / 60),
        }}
      >
        TODO · drop a real recording into public/demo-library.mp4
      </p>
    </AbsoluteFill>
  );
};
