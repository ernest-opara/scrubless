import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Cursor } from "../components/Cursor";
import { theme } from "../theme";

/**
 * Scene 7 (0:44-0:52) — four 2-second cutaways. Each cutaway is the SAME
 * gesture as scene 1 (someone scrubbing) — except this time it resolves
 * into the typed query landing them on the right moment.
 *
 * Recommended path: drop four 2-second mp4s into public/b-roll/ named
 *   creator.mp4, podcaster.mp4, family.mp4, team.mp4
 * Each clip just needs to look like the named context — desk + headphones,
 * couch with a tablet, meeting room, etc. Stock works fine; AI stills
 * timed over a Ken-Burns pan work too.
 *
 * Without those mp4s, we fall back to four typography cards so the scene
 * keeps the right pacing.
 */
const CUTAWAY_FRAMES = 60; // 2s each at 30fps
const USE_REAL_BROLL = false;

const CUTAWAYS = [
  { id: "creator", label: "For creators", file: "b-roll/creator.mp4" },
  { id: "podcaster", label: "For podcasters", file: "b-roll/podcaster.mp4" },
  { id: "family", label: "For families", file: "b-roll/family.mp4" },
  { id: "team", label: "For teams", file: "b-roll/team.mp4" },
];

const Cutaway: React.FC<{ index: number }> = ({ index }) => {
  const cut = CUTAWAYS[index];
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [CUTAWAY_FRAMES - 10, CUTAWAY_FRAMES],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{
        background: theme.bg,
        opacity: Math.min(fadeIn, fadeOut),
      }}
    >
      {USE_REAL_BROLL ? (
        <OffthreadVideo
          src={staticFile(cut.file)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : (
        <AbsoluteFill
          style={{
            alignItems: "center",
            justifyContent: "center",
            background:
              index % 2 === 0 ? theme.bg : theme.bgSoft,
          }}
        >
          {/* Stand-in poster */}
          <div
            style={{
              width: 760,
              height: 440,
              background: theme.bgCard,
              border: `1px solid ${theme.line}`,
              borderRadius: 18,
              boxShadow: theme.shadowSm,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <p
              style={{
                fontFamily: theme.fontMono,
                fontSize: 13,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: theme.accent,
                margin: 0,
              }}
            >
              TODO · public/{cut.file}
            </p>
            <p
              style={{
                fontFamily: theme.fontDisplay,
                fontSize: 56,
                color: theme.fg,
                margin: 0,
              }}
            >
              {cut.label.replace("For ", "")}
            </p>
          </div>
        </AbsoluteFill>
      )}

      {/* Lower-third caption — runs over real B-roll too */}
      <div
        style={{
          position: "absolute",
          left: 80,
          bottom: 80,
          fontFamily: theme.fontMono,
          fontSize: 22,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: theme.bgDark,
          background: theme.bgCard,
          padding: "10px 18px",
          borderRadius: 999,
          boxShadow: theme.shadowSm,
        }}
      >
        {cut.label}
      </div>
    </AbsoluteFill>
  );
};

export const UseCasesScene: React.FC = () => {
  return (
    <>
      {CUTAWAYS.map((_, i) => (
        <Sequence
          key={i}
          from={i * CUTAWAY_FRAMES}
          durationInFrames={CUTAWAY_FRAMES}
        >
          <Cutaway index={i} />
        </Sequence>
      ))}
    </>
  );
};
