import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { loadFont } from "@remotion/google-fonts/InstrumentSerif";
import { SCENES, theme } from "../theme";
import { PainScene } from "../scenes/01-PainScene";
import { BridgeScene } from "../scenes/02-BridgeScene";
import { RevealScene } from "../scenes/03-RevealScene";
import { DemoSingleScene } from "../scenes/04-DemoSingleScene";
import { DemoLibraryScene } from "../scenes/05-DemoLibraryScene";
import { DemoAskScene } from "../scenes/06-DemoAskScene";
import { UseCasesScene } from "../scenes/07-UseCasesScene";
import { HeadlineScene } from "../scenes/08-HeadlineScene";
import { CTAScene } from "../scenes/09-CTAScene";
import { StampScene } from "../scenes/10-StampScene";

loadFont(); // makes Instrument Serif available everywhere

/** Each scene's start frame, computed from the durations in theme.ts. */
const cumulative = (() => {
  const order = [
    "PAIN",
    "BRIDGE",
    "REVEAL",
    "DEMO_SINGLE",
    "DEMO_LIBRARY",
    "DEMO_ASK",
    "USE_CASES",
    "HEADLINE",
    "CTA",
    "STAMP",
  ] as const;
  const starts: Record<(typeof order)[number], number> = {} as any;
  let acc = 0;
  for (const k of order) {
    starts[k] = acc;
    acc += SCENES[k];
  }
  return starts;
})();

export const MarketingVideo: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: theme.bg }}>
      <Sequence from={cumulative.PAIN} durationInFrames={SCENES.PAIN}>
        <PainScene />
      </Sequence>
      <Sequence from={cumulative.BRIDGE} durationInFrames={SCENES.BRIDGE}>
        <BridgeScene />
      </Sequence>
      <Sequence from={cumulative.REVEAL} durationInFrames={SCENES.REVEAL}>
        <RevealScene />
      </Sequence>
      <Sequence
        from={cumulative.DEMO_SINGLE}
        durationInFrames={SCENES.DEMO_SINGLE}
      >
        <DemoSingleScene />
      </Sequence>
      <Sequence
        from={cumulative.DEMO_LIBRARY}
        durationInFrames={SCENES.DEMO_LIBRARY}
      >
        <DemoLibraryScene />
      </Sequence>
      <Sequence from={cumulative.DEMO_ASK} durationInFrames={SCENES.DEMO_ASK}>
        <DemoAskScene />
      </Sequence>
      <Sequence
        from={cumulative.USE_CASES}
        durationInFrames={SCENES.USE_CASES}
      >
        <UseCasesScene />
      </Sequence>
      <Sequence from={cumulative.HEADLINE} durationInFrames={SCENES.HEADLINE}>
        <HeadlineScene />
      </Sequence>
      <Sequence from={cumulative.CTA} durationInFrames={SCENES.CTA}>
        <CTAScene />
      </Sequence>
      <Sequence from={cumulative.STAMP} durationInFrames={SCENES.STAMP}>
        <StampScene />
      </Sequence>
    </AbsoluteFill>
  );
};
