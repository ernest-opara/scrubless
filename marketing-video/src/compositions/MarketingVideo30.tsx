import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { loadFont } from "@remotion/google-fonts/InstrumentSerif";
import { FPS, theme } from "../theme";
import { PainScene } from "../scenes/01-PainScene";
import { BridgeScene } from "../scenes/02-BridgeScene";
import { DemoSingleScene } from "../scenes/04-DemoSingleScene";
import { HeadlineScene } from "../scenes/08-HeadlineScene";
import { CTAScene } from "../scenes/09-CTAScene";

loadFont();

/**
 * Trimmed 30s cut for social / pre-roll. Same scenes, condensed:
 * pain (3s) → bridge (3s) → single-video demo (12s) → headline (6s) → CTA (6s).
 */
export const MarketingVideo30: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: theme.bg }}>
      <Sequence from={0} durationInFrames={3 * FPS}>
        <PainScene />
      </Sequence>
      <Sequence from={3 * FPS} durationInFrames={3 * FPS}>
        <BridgeScene />
      </Sequence>
      <Sequence from={6 * FPS} durationInFrames={12 * FPS}>
        <DemoSingleScene />
      </Sequence>
      <Sequence from={18 * FPS} durationInFrames={6 * FPS}>
        <HeadlineScene />
      </Sequence>
      <Sequence from={24 * FPS} durationInFrames={6 * FPS}>
        <CTAScene />
      </Sequence>
    </AbsoluteFill>
  );
};
