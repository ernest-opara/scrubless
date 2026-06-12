import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { theme } from "../theme";

/**
 * Scene 2 (0:04-0:08) — black hold. One italic line fades up centered, then
 * out. The breath between the pain and the reveal; music should drop to a
 * sustained note here.
 */
export const BridgeScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = spring({
    fps,
    frame: frame - 10,
    config: { damping: 18, mass: 0.6 },
  });
  const fadeOut = interpolate(frame, [90, 115], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = Math.min(fadeIn, fadeOut);

  return (
    <AbsoluteFill
      style={{
        background: "#000",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 8%",
      }}
    >
      <p
        style={{
          opacity,
          fontFamily: theme.fontDisplay,
          fontStyle: "italic",
          fontSize: 84,
          color: theme.fgInverse,
          textAlign: "center",
          margin: 0,
          letterSpacing: "-0.012em",
          lineHeight: 1.1,
        }}
      >
        There's a better way to find a moment.
      </p>
    </AbsoluteFill>
  );
};
