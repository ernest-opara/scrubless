import React from "react";
import { Composition } from "remotion";
import { MarketingVideo } from "./compositions/MarketingVideo";
import { MarketingVideo30 } from "./compositions/MarketingVideo30";
import { MarketingVideoSquare } from "./compositions/MarketingVideoSquare";
import { FPS, TOTAL_FRAMES } from "./theme";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 75-second hero — 1920x1080, the master render */}
      <Composition
        id="MarketingVideo"
        component={MarketingVideo}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
      />

      {/* 30-second social cut — same composition, scene set trimmed */}
      <Composition
        id="MarketingVideo30"
        component={MarketingVideo30}
        durationInFrames={30 * FPS}
        fps={FPS}
        width={1920}
        height={1080}
      />

      {/* 1:1 social square — 1080x1080 for Instagram feed / X timeline */}
      <Composition
        id="MarketingVideoSquare"
        component={MarketingVideoSquare}
        durationInFrames={30 * FPS}
        fps={FPS}
        width={1080}
        height={1080}
      />
    </>
  );
};
