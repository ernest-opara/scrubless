import React from "react";
import { Sequence } from "remotion";
import { ScrubberHand } from "../components/ScrubberHand";
import { FPS } from "../theme";

/**
 * Scene 1 (0:00-0:04) — three tight macro shots of someone dragging a video
 * scrubber back-and-forth, ~1.2-1.3s each. The same gesture, three different
 * "screens." Scrub SFX go here in the audio bed (see README → Audio).
 */
const SHOT = Math.round(FPS * 1.33); // ~1.33s per scrubber

export const PainScene: React.FC = () => {
  return (
    <>
      <Sequence from={0} durationInFrames={SHOT}>
        <ScrubberHand startFrame={0} duration="0:00 / 1:34:12" />
      </Sequence>
      <Sequence from={SHOT} durationInFrames={SHOT}>
        <ScrubberHand startFrame={0} duration="00:14 / 45:08" />
      </Sequence>
      <Sequence from={SHOT * 2} durationInFrames={SHOT}>
        <ScrubberHand startFrame={0} duration="LIVE · 02:43:09" />
      </Sequence>
    </>
  );
};
