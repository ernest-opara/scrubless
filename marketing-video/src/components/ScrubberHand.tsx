import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { theme } from "../theme";

/**
 * One of the three scrubbing-finger macros that opens the video. Renders a
 * stylised player timeline with a thumb dragging back-and-forth — kept
 * abstract on purpose so it reads on any aspect.
 */
export const ScrubberHand: React.FC<{
  startFrame: number;
  /** Label under the player, e.g. "0:00 / 1:34:12" */
  duration: string;
}> = ({ startFrame, duration }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = Math.max(0, frame - startFrame);
  const t = localFrame / fps; // seconds into this scrubber

  // Position oscillates back-and-forth between 25% and 80% twice per second.
  const x = interpolate(
    Math.sin(t * Math.PI * 2.4),
    [-1, 1],
    [0.25, 0.80]
  );

  return (
    <AbsoluteFill
      style={{
        background: theme.bgDark,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Player area */}
      <div
        style={{
          width: "78%",
          aspectRatio: "16 / 9",
          background: "#0a0a0c",
          borderRadius: 14,
          position: "relative",
          overflow: "hidden",
          boxShadow: theme.shadowMd,
        }}
      >
        {/* dim "frame still" */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(60% 60% at 30% 40%, rgba(255,255,255,0.05) 0%, transparent 70%)",
          }}
        />
        {/* timeline */}
        <div
          style={{
            position: "absolute",
            left: 24,
            right: 24,
            bottom: 24,
            height: 6,
            background: "rgba(255,255,255,0.18)",
            borderRadius: 999,
          }}
        >
          {/* progress fill */}
          <div
            style={{
              height: "100%",
              width: `${x * 100}%`,
              background: "rgba(255,255,255,0.6)",
              borderRadius: 999,
            }}
          />
          {/* the dragging thumb */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: `${x * 100}%`,
              transform: "translate(-50%, -50%)",
              width: 18,
              height: 18,
              borderRadius: "50%",
              background: "#fff",
              boxShadow: "0 1px 6px rgba(0,0,0,0.4)",
            }}
          />
        </div>

        {/* the finger — stylised, just a soft rounded blob with a fingernail */}
        <div
          style={{
            position: "absolute",
            left: `calc(24px + ${x * 100}% - 24px)`,
            bottom: 6,
            width: 60,
            height: 80,
            background: "#f3d4a8",
            borderRadius: "50% 50% 38% 38% / 60% 60% 40% 40%",
            transform: "translateX(-50%) rotate(-12deg)",
            boxShadow: "0 6px 18px rgba(0,0,0,0.35)",
          }}
        >
          {/* fingernail */}
          <div
            style={{
              position: "absolute",
              top: 6,
              left: 16,
              width: 24,
              height: 14,
              background: "#fce8c5",
              borderRadius: "50% 50% 30% 30%",
            }}
          />
        </div>
      </div>

      {/* tiny duration label so the player feels real */}
      <div
        style={{
          marginTop: 18,
          fontFamily: theme.fontMono,
          color: "rgba(255,255,255,0.55)",
          fontSize: 14,
          letterSpacing: "0.08em",
        }}
      >
        {duration}
      </div>
    </AbsoluteFill>
  );
};
