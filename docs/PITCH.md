---
title: "Scrubless"
subtitle: "Stop scrubbing. Start searching."
author: "Ernest Opara"
institute: "getscrubless.com"
date: "May 2026"
theme: "metropolis"
themeoptions:
  - "progressbar=frametitle"
  - "numbering=fraction"
aspectratio: 169
fontsize: 11pt
mainfont: "Helvetica Neue"
monofont: "Menlo"
colorlinks: true
linkcolor: "RoyalBlue"
urlcolor: "RoyalBlue"
slide-level: 2
header-includes: |
  \usepackage{newunicodechar}
  \newunicodechar{→}{\ensuremath{\rightarrow}}
  \newunicodechar{≤}{\ensuremath{\leq}}
  \newunicodechar{·}{\textperiodcentered}
  \newunicodechar{⟨}{\ensuremath{\langle}}
  \newunicodechar{⟩}{\ensuremath{\rangle}}
  \definecolor{scrubcoral}{HTML}{E0623E}
  \definecolor{scrubcharcoal}{HTML}{1F2125}
  \setbeamercolor{normal text}{fg=scrubcharcoal, bg=white}
  \setbeamercolor{alerted text}{fg=scrubcoral}
  \setbeamercolor{progress bar}{fg=scrubcoral}
  \setbeamercolor{title separator}{fg=scrubcoral}
  \setbeamercolor{frametitle}{bg=scrubcharcoal, fg=white}
  \setbeamercolor{progress bar in head/foot}{fg=scrubcoral}
---

## The problem

**Video is the one medium you still can't search.**

- 500+ hours are uploaded to YouTube *every minute* — and that's one platform.
- Inside any single video, finding a moment means \alert{scrubbing}: linear,
  manual, slow.
- `Ctrl+F` solved this for text 40 years ago.
- There is still no `Ctrl+F` for video.

> The world's fastest-growing data type is also its least searchable.

## The solution

**Scrubless is `Ctrl+F` for video.**

- Upload a video — or point Scrubless at a whole folder of them.
- Search in plain English: *"the part where someone is laughing."*
- Click a result and the player jumps to that \alert{exact second}.
- It searches what's **shown** and what's **said** — not just captions.

## How it works

One pipeline turns every video into three searchable signals.

![](diagrams/pitch-flow.pdf){width=92%}

\footnotesize
Frames become **CLIP** vectors (the visuals), audio becomes a **Whisper**
transcript (the words), and **Claude** turns retrieved moments into cited
answers. One search box over all of it.

## More than search

Once a video is indexed, the hard part is done — everything else is free.

- **Library mode** — search across an *entire folder* of videos at once.
- **Ask** — questions answered in prose, with clickable cited timestamps.
- **Auto-chapters & summaries** generated on every upload.
- **Highlight reels** — stitch the best moments into a shareable clip.

> Index once. Search, ask, summarize, and cut — from the same index.

## Why now

The pieces only just became cheap enough to put in one small app.

- **Multimodal embeddings** (CLIP) are good, fast, and open.
- **Whisper** drove transcription cost toward zero.
- **LLMs** (Claude) can now reason over retrieved moments and cite them.
- **Video volume** is compounding while tooling stays stuck on scrubbing.

\alert{The capability exists. The product doesn't — yet.}

## Market

Every video library is a search problem waiting to happen.

- **Creators & editors** — find the take, the b-roll, the clip.
- **Teams** — meetings, training, support calls, all-hands archives.
- **Enterprise & regulated** — media, legal, security, compliance footage.

Bottom-up, the wedge is anyone sitting on hours of video they can't find their
way through.

\footnotesize *TAM — video management + enterprise search: ⟨insert your sizing here⟩.*

## Traction

Live in production today at **getscrubless.com**:

- **V1** — semantic search inside a video.
- **V2** — library mode across a folder of videos, durable per-user storage.
- **V3** — Q&A with citations, auto-chapters, highlight reels.
- Auth and **Stripe billing** shipped and working.

\footnotesize *⟨Add real metrics here: signups / waitlist / paying users / minutes
indexed / week-over-week growth.⟩*

## Business model

Freemium SaaS, priced on what costs us money: **indexed hours**.

- **Free** — a few minutes to feel the magic.
- **Pro** — monthly plan by indexed hours, self-serve via Stripe.
- **Expansion** — team seats, API access, on-prem / enterprise.

\footnotesize Cheap to run: one process, model and vector DB in-memory, fits on a
single small instance — gross margin is on our side.

## Competition

| Approach | What they do | The gap |
|---|---|---|
| Transcript search | Find spoken **words** | Blind to visuals |
| DAM / MAM incumbents | Manual tags, enterprise-heavy | Not semantic, slow to adopt |
| Big-platform search | Search **their** content | Locked in; not your files |

\vspace{0.5em}
**Our wedge:** visual **+** spoken semantic search, dead-simple, running on *your
own* videos.

## Team

- **Ernest Opara** — founder. *⟨background, prior work, why you're the one to
  build this.⟩*
- *⟨co-founders / early team / advisors, if any.⟩*

\vspace{0.5em}
Built and shipped the entire product — V1 through V3, auth, and billing — solo,
to production.

## Vision & the ask

**The index layer for the world's video.** Every clip, meeting, lecture, and
archive — instantly searchable, anywhere it lives.

\vspace{0.5em}

- **Raising** *⟨amount⟩* to *⟨growth · key hires · enterprise⟩*.
- Try it now: [getscrubless.com](https://getscrubless.com)
- [e@getscrubless.com](mailto:e@getscrubless.com)

\begin{center}
\alert{\Large Stop scrubbing. Start searching.}
\end{center}
