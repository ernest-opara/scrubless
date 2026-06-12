import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { loadFont } from "@remotion/google-fonts/InstrumentSerif";
import { FPS, theme } from "../theme";
import { PainScene } from "../scenes/01-PainScene";
import { HeadlineScene } from "../scenes/08-HeadlineScene";
import { CTAScene } from "../scenes/09-CTAScene";

loadFont();

/**
 * 1:1 square cut for Instagram feed + X timeline. 30 seconds total. We
 * keep the strongest beats (pain → headline → CTA) and let the same scene
 * components reflow to the square aspect; the layouts are mostly centered
 * so they hold up in 1080x1080.
 */
export const MarketingVideoSquare: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: theme.bg }}>
      <Sequence from={0} durationInFrames={5 * FPS}>
        <PainScene />
      </Sequence>
      <Sequence from={5 * FPS} durationInFrames={15 * FPS}>
        <HeadlineScene />
      </Sequence>
      <Sequence from={20 * FPS} durationInFrames={10 * FPS}>
        <CTAScene />
      </Sequence>
    </AbsoluteFill>
  );
};
