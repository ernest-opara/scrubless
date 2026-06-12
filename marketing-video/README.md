# Scrubless · marketing-video

Remotion project that renders the Scrubless launch video — 75 seconds, 1920×1080
at 30 fps, plus a trimmed 30s social cut and a 1:1 square. The storyboard from
`docs/STORYBOARD.md` (or wherever you keep it) is implemented as React
components, one per scene, so iterating timing is a code change.

## Run

```bash
cd marketing-video
npm install               # ~2-4 min the first time
npm run dev               # opens Remotion Studio at http://localhost:3000
```

Studio gives you a timeline scrubber, audio waveform, and per-frame preview.
The three compositions in the sidebar:

| Composition | Duration | Use |
|---|---|---|
| `MarketingVideo` | 75s · 1920×1080 | Master render — landing page hero, YouTube |
| `MarketingVideo30` | 30s · 1920×1080 | Pre-roll, paid ads |
| `MarketingVideoSquare` | 30s · 1080×1080 | Instagram feed, X timeline |

## Render

```bash
npm run render            # writes out/scrubless-marketing.mp4
npm run render-30s        # 30s cut
npm run render-square     # 1:1 square cut
```

Final renders go to `out/` (gitignored).

## What renders out of the box

All ten scenes compile and render *something* immediately — no missing
assets, no errors. The opening pain hook, headline, CTA, and end-card scenes
are production-ready as-is.

The three demo scenes and the use-cases montage render synthetic placeholders
that hold the right pacing and aesthetic. You replace those with real footage
when you have it — see below.

## Swapping in real footage

The demo scenes (4, 5, 6) and the use-cases montage (7) each have a
`USE_REAL_RECORDING` (or `USE_REAL_BROLL`) flag at the top. Flip it to
`true` once the file exists in `public/`:

```ts
// src/scenes/04-DemoSingleScene.tsx
const USE_REAL_RECORDING = true;
```

Drop the files in `public/`:

| File | Scene | What it should show |
|---|---|---|
| `public/demo-single.mp4` | 04 | Search inside one video on getscrubless.com — type a query, hit search, click a result, player jumps |
| `public/demo-library.mp4` | 05 | Open a folder, type a query, results from multiple videos, click one |
| `public/demo-ask.mp4` | 06 | Ask tab, type a question, answer renders with clickable citations, click one |
| `public/b-roll/creator.mp4` | 07 | 2s of someone at a desk/editing bay |
| `public/b-roll/podcaster.mp4` | 07 | 2s of someone with headphones / mic |
| `public/b-roll/family.mp4` | 07 | 2s of someone on a couch with a tablet |
| `public/b-roll/team.mp4` | 07 | 2s of a meeting room / call |

Record screen captures at **1920×1080, 60fps minimum**. Trim to the exact
duration of the scene (10s for the demos, 2s for each B-roll cutaway).
Remotion handles the playback rate, but matching duration prevents cuts.

## Editing the storyboard

Scene durations live in [`src/theme.ts`](src/theme.ts) in the `SCENES`
object. Adjust a number, save, the timeline updates. Total length is
derived, so the master composition stays in sync.

```ts
export const SCENES = {
  PAIN: 120,     // 4s @ 30fps
  REVEAL: 180,   // 6s
  ...
};
```

To rearrange scenes, edit the `Sequence` order in
[`src/compositions/MarketingVideo.tsx`](src/compositions/MarketingVideo.tsx).

## Brand tokens

All colors and fonts live in [`src/theme.ts`](src/theme.ts). Changing the
indigo accent there flows through every scene automatically. Stays in sync
with the production landing page's `scrubby/scrubless.css`.

## Audio

This scaffold renders **silent** video. Audio is layered separately because
you'll iterate on it more than the visuals:

1. **VO** — record yourself or use a service (ElevenLabs $5/mo, Fiverr $50–200
   for a polished voice). Save as `public/vo.mp3`.
2. **Music bed** — Epidemic Sound, Musicbed, or YouTube's free library. ~30
   BPM bedding. Save as `public/music.mp3`.
3. **SFX** — `scrub-scrub.mp3` for scene 1 (three short ratchets), `click.mp3`
   for scene 4. Freesound.org has good free options.

To wire them in, edit `src/compositions/MarketingVideo.tsx`:

```tsx
import { Audio, staticFile } from "remotion";

<Audio src={staticFile("music.mp3")} volume={0.4} />
<Audio src={staticFile("vo.mp3")} />
```

Mix in post (the VO sits +6dB above the music; SFX -3dB below the VO).

## Per-scene render budget

If a single scene is slow to iterate (the demos sometimes are because of the
video decoding), render it solo:

```bash
npx remotion render MarketingVideo out/scrubless-marketing.mp4 \
  --frames=420-720       # scene 4 only
```

## Directory map

```
marketing-video/
├── package.json
├── tsconfig.json
├── remotion.config.ts
├── README.md
├── public/                     # static assets (mp4s, audio, images)
│   ├── scrubby.png             # mascot, end card
│   ├── demo-*.mp4              # real product recordings (you record)
│   ├── b-roll/*.mp4            # lifestyle cutaways (you record/source)
│   └── music.mp3 / vo.mp3      # audio (you record)
└── src/
    ├── index.ts                # Remotion entry
    ├── Root.tsx                # composition registration
    ├── theme.ts                # brand tokens + scene timings
    ├── compositions/           # the three video lengths
    ├── components/             # Cursor, Eyebrow, UnderlineWord, ScrubberHand
    └── scenes/                 # 01..10, one component per storyboard scene
```

## Notes

- **First render is slow** (a few minutes). Remotion is bundling everything
  the first time. Subsequent renders are much faster (~30s for a full pass
  with no real video files; longer with mp4 inputs).
- **CRF in remotion.config.ts is set to 18** — visually lossless, file size
  ~80-120 MB for the 75s master. Bump to 23-25 if you need smaller files for
  social uploads.
- **Mobile rendering** — Remotion runs headless Chrome to render. Memory
  spikes during long renders are normal. If you OOM, render in chunks with
  `--frames=START-END` and stitch with ffmpeg.
