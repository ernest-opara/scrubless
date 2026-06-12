import React from "react";
import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Cursor } from "../components/Cursor";
import { theme } from "../theme";

/**
 * Scene 4 (0:14-0:24) — single-video demo. Two ways to use this scene:
 *
 *   (A) RECOMMENDED — Real screen recording.
 *       Record a 10-second clip of you searching the sample on getscrubless.com
 *       (type "the big rabbit", hit search, click a result, let the player
 *       jump). Save as public/demo-single.mp4 and the OffthreadVideo below
 *       will play it. Drop the synthetic UI block (the JSX in the fallback)
 *       and you're done.
 *
 *   (B) FALLBACK — Synthetic UI mock.
 *       The block below renders a stylised typing animation + result cards
 *       so the scene compiles before you record. Good for previewing the
 *       overall pacing.
 */
const USE_REAL_RECORDING = false; // flip to true once demo-single.mp4 exists

export const DemoSingleScene: React.FC = () => {
  const frame = useCurrentFrame();

  if (USE_REAL_RECORDING) {
    return (
      <AbsoluteFill style={{ background: theme.bg }}>
        <OffthreadVideo
          src={staticFile("demo-single.mp4")}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
    );
  }

  // ---- Synthetic mock ----
  const TYPING_START = 18;
  const TYPING_END = 78;
  const RESULTS_START = 100;
  const CLICK_FRAME = 180;

  const query = "the part where she's laughing";
  const typed = query.slice(
    0,
    Math.max(
      0,
      Math.round(
        interpolate(
          frame,
          [TYPING_START, TYPING_END],
          [0, query.length],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        )
      )
    )
  );
  const showCaret = Math.floor(frame / 8) % 2 === 0;

  // Cursor moves to "Search" button between frames 80 and 100, then dips
  // to a result card around frame 170.
  const cursorX = interpolate(
    frame,
    [0, 80, 100, 170, 180],
    [1500, 1500, 1640, 1180, 1180],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const cursorY = interpolate(
    frame,
    [0, 80, 100, 170, 180],
    [820, 220, 220, 480, 480],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Result cards stagger in after RESULTS_START
  const result = (i: number) => {
    const t = interpolate(
      frame,
      [RESULTS_START + i * 8, RESULTS_START + i * 8 + 16],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    return { opacity: t, transform: `translateY(${(1 - t) * 14}px)` };
  };

  const playerJumped = frame >= CLICK_FRAME;

  return (
    <AbsoluteFill style={{ background: theme.bg, padding: 80 }}>
      {/* Browser-y window chrome */}
      <div
        style={{
          background: theme.bgCard,
          borderRadius: 16,
          padding: 18,
          height: "100%",
          boxShadow: theme.shadowMd,
          display: "grid",
          gridTemplateColumns: "1.5fr 1fr",
          gap: 24,
        }}
      >
        {/* Player column */}
        <div
          style={{
            background: theme.bgDark,
            borderRadius: 12,
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Without recording, render a stand-in "frame still" */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: playerJumped
                ? "radial-gradient(60% 60% at 35% 45%, #fde9b8 0%, #1f1d23 75%)"
                : "linear-gradient(135deg, #1f1d23 0%, #0a0a0c 100%)",
              transition: "background 0.3s",
            }}
          />
          {/* mock timeline */}
          <div
            style={{
              position: "absolute",
              left: 18,
              right: 18,
              bottom: 18,
              height: 4,
              background: "rgba(255,255,255,0.2)",
              borderRadius: 999,
            }}
          >
            <div
              style={{
                height: "100%",
                width: playerJumped ? "32%" : "0%",
                background: theme.accent,
                borderRadius: 999,
                transition: "width 0.25s",
              }}
            />
          </div>
        </div>

        {/* Search + results column */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            padding: 8,
          }}
        >
          {/* Search input */}
          <div
            style={{
              display: "flex",
              gap: 8,
              padding: "12px 18px",
              background: theme.bg,
              border: `1px solid ${theme.line}`,
              borderRadius: 999,
              fontFamily: theme.fontBody,
              fontSize: 20,
              color: theme.fg,
            }}
          >
            <span>{typed || (
              <span style={{ color: theme.fgFaint }}>
                find the part where someone is laughing
              </span>
            )}</span>
            {typed && showCaret && (
              <span style={{ color: theme.accent }}>|</span>
            )}
          </div>

          {/* Result cards */}
          {[
            { t: "0:18", pct: 97 },
            { t: "1:42", pct: 95 },
            { t: "3:05", pct: 92 },
            { t: "0:34", pct: 87 },
          ].map((r, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 12,
                padding: 14,
                background: theme.bg,
                border: `1px solid ${theme.line}`,
                borderRadius: 12,
                ...result(i),
              }}
            >
              <div
                style={{
                  width: 132,
                  height: 74,
                  background:
                    "linear-gradient(135deg, #d6f0d8 0%, #94c39c 100%)",
                  borderRadius: 8,
                  flexShrink: 0,
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span
                    style={{
                      fontFamily: theme.fontMono,
                      fontSize: 16,
                      color: theme.fg,
                    }}
                  >
                    {r.t}
                  </span>
                  <span
                    style={{
                      fontFamily: theme.fontMono,
                      background: theme.accent,
                      color: theme.accentInk,
                      padding: "3px 10px",
                      borderRadius: 999,
                      fontSize: 13,
                    }}
                  >
                    {r.pct}% match
                  </span>
                </div>
                <p
                  style={{
                    color: theme.fgMuted,
                    fontSize: 15,
                    margin: "4px 0 0",
                  }}
                >
                  Matched moment
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Cursor x={cursorX} y={cursorY} />
    </AbsoluteFill>
  );
};
