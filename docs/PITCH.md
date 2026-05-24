---
title: "Scrubless"
subtitle: "Stop scrubbing. Start searching."
author: "Chukwuebuka Ernest-Opara"
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
  \newunicodechar{×}{\ensuremath{\times}}
  \newunicodechar{≈}{\ensuremath{\approx}}
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

**TAM ≈ \$30B / year** — the global spend on making video findable.

Bottom-up:

- **50M** pro / prosumer video creators × \$240/yr (Pro) = **\$12B**
- **30M** businesses with video archives × \$600/yr (Team) = **\$18B**

\vspace{0.3em}

- **SAM ≈ \$7B** — English-first, self-serve + mid-market reachable today.
- **SOM ≈ \$50-150M** — realistic capture in 3-5 years.

\footnotesize Top-down cross-check: digital asset management (≈\$5B), enterprise
search (≈\$6B), and video intelligence (≈\$11B) target the same need and
triangulate to the same order of magnitude.

## Traction

**Shipped and live** at getscrubless.com:

- V1 search, V2 library mode, V3 Q&A / chapters / reels — all in production.
- Auth + Stripe billing working; durable per-user storage.

**Targets — next two quarters, post public launch:**

- **1,000** signups in the first 90 days (Show HN / Product Hunt).
- **100** paying customers and **\$2K MRR** by end of Q3 2026.
- **10,000** hours of video indexed.
- **40%** week-4 retention on activated users.

\footnotesize Targets, not actuals — swap in live numbers as they land.

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

**Chukwuebuka Ernest-Opara** — founder & sole engineer.

- Designed, built, and shipped the **entire product solo** — V1 through V3, auth,
  and Stripe billing — to production.
- *⟨prior background: engineering roles / education / domain — fill in.⟩*

\vspace{0.4em}
**In talks with two co-founders** with media experience to lead content and
go-to-market.

\footnotesize One technical founder who ships fast — a media-savvy founding team
forming around a product that already works.

## Vision

**The index layer for the world's video.** Every clip, meeting, lecture, and
archive — instantly searchable, anywhere it lives.

\vspace{0.4em}
Search was the gateway to the web. Scrubless is that gateway for video.

\vspace{1.2em}
\begin{center}
\alert{\Large Stop scrubbing. Start searching.}
\end{center}

\vspace{0.8em}
\begin{center}
\footnotesize getscrubless.com \quad·\quad e@getscrubless.com
\end{center}
