import React from "react";
import {
  AbsoluteFill,
  interpolate,
  Img,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { theme } from "../theme";

/**
 * Scene 10 (1:08-1:15) — quiet end card. Wordmark + Scrubby + URL on cream,
 * held for ~7 seconds. Drop scrubby.png into public/ so the Img picks it up.
 */
export const StampScene: React.FC = () => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 18], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: theme.bg,
        alignItems: "center",
        justifyContent: "center",
        opacity: fadeIn,
        gap: 32,
      }}
    >
      {/* Scrubby — drop scrubby.png into public/ (a copy of
          scrubby/png/02-mascot-yellow.png from the main repo) */}
      <Img
        src={staticFile("scrubby.png")}
        style={{ width: 220, height: "auto" }}
      />
      <p
        style={{
          fontFamily: theme.fontDisplay,
          fontSize: 88,
          color: theme.fg,
          margin: 0,
          letterSpacing: "-0.005em",
        }}
      >
        Scrubless
      </p>
      <p
        style={{
          fontFamily: theme.fontMono,
          fontSize: 22,
          letterSpacing: "0.12em",
          color: theme.fgMuted,
          textTransform: "lowercase",
          margin: 0,
        }}
      >
        getscrubless.com
      </p>
    </AbsoluteFill>
  );
};
