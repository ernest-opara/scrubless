---
title: "Scrubless: Natural-Language Moment Retrieval in Personal Video with Zero-Shot Vision–Language Embeddings"
subtitle: "Project report"
author: "Chukwuebuka Ernest-Opara"
date: "September 2026"
abstract: |
  Finding a specific moment inside a long video still means scrubbing a timeline
  by hand. This report describes Scrubless, a system I designed, built, and
  deployed that lets a user upload a video and retrieve moments with a natural-
  language query, and it evaluates the retrieval method the system ships with.
  Scrubless samples one frame every five seconds, embeds each frame with a
  contrastively trained vision–language model (OpenCLIP ViT-B/32), stores the
  vectors in an in-process vector database, and ranks frames by cosine
  similarity to the embedded query; the speech track is transcribed and attached
  to each frame's window as metadata. I constructed a 65-query benchmark over
  three openly licensed videos (30 minutes in total), labelled with ground-truth
  time intervals and split into *visual* and *spoken* queries, and measured
  Recall@k and mean reciprocal rank under nine ranking conditions. The shipped,
  vision-only ranker performs well on visual queries (Recall@1 = 0.77) but is
  almost blind to spoken content (Recall@1 = 0.12). Lexical retrieval over the
  transcript shows the opposite profile. The obvious remedy, rank fusion, is not
  free: reciprocal-rank fusion and max-normalised score fusion both *lower*
  top-1 accuracy on visual queries by roughly half. I trace the loss to the
  normalisation step, which inflates weak lexical matches, and show that
  normalising BM25 by the query's attainable score (an idf-weighted measure of
  query coverage) removes the loss without tuning: the resulting hybrid ranker
  reaches Recall@1 = 0.80 and MRR = 0.85 on the full benchmark, against 0.51 and
  0.58 for the shipped system, with no additional model and negligible latency.
  Leave-one-video-out selection of the single fusion weight confirms the result
  is not an artefact of tuning on the test set. I also quantify two smaller
  effects: denser frame sampling does not improve top-1 accuracy, and near-
  uniform (black) frames act as hubs in the embedding space and can be removed
  at index time.
numbersections: true
geometry: "margin=1in"
fontsize: 11pt
linkcolor: "RoyalBlue"
urlcolor: "RoyalBlue"
colorlinks: true
header-includes: |
  \usepackage{newunicodechar}
  \newunicodechar{→}{\ensuremath{\rightarrow}}
  \newunicodechar{≤}{\ensuremath{\leq}}
  \newunicodechar{≥}{\ensuremath{\geq}}
  \newunicodechar{α}{\ensuremath{\alpha}}
  \newunicodechar{Σ}{\ensuremath{\Sigma}}
  \newunicodechar{±}{\ensuremath{\pm}}
  \newunicodechar{×}{\ensuremath{\times}}
  \usepackage{booktabs}
  \usepackage{float}
  \floatplacement{figure}{H}
---

\newpage

# Introduction

Video is the medium in which the most information is recorded and the least is
retrievable. A two-hour recording of a meeting, a lecture, or a family event
contains a handful of moments that anyone will ever want again, and the only
general tool for reaching them is the scrub bar. Text search inside a document
is instantaneous; the equivalent operation inside a video, "take me to the part
where someone opens the gift," has no widely available implementation for
personal media.

Scrubless is my attempt to build that operation as a product rather than as a
research prototype. The user story is one sentence: upload a video, type what
you are looking for, click the result, and the player jumps to that moment. The
system is deployed at getscrubless.com and has been used by external users; the
present report, however, is about the retrieval method at its core and about
how well that method actually works.

The method is deliberately simple. Recent vision–language models trained
contrastively on image–caption pairs, of which CLIP [14] is the
canonical example, place images and free-text descriptions in a shared
embedding space in which cosine similarity is meaningful across modalities.
Treating a video as a sparse sequence of still frames turns moment retrieval
into nearest-neighbour search: embed every frame once, embed the query at
search time, and return the frames whose vectors lie closest to the query
vector. No task-specific training is needed, and the whole pipeline fits in one
Python process on a laptop or a small virtual server.

That simplicity raises an obvious question, which the product's early users
raised in a more pointed form: what happens when the moment is defined by what
was *said* rather than by what was *shown*? The frame embedding contains no
information about speech. Scrubless transcribes the audio track and attaches
the transcript to each frame's time window, but the shipped ranking function
ignores it. I had no measurement of how much this cost.

This report makes the following contributions.

1. A description of the system as built and deployed, with the design
   constraints that shaped it (Section 3).
2. A small but carefully constructed retrieval benchmark: 65 natural-language
   queries with ground-truth time intervals over three openly licensed videos,
   split by whether the target moment is visually or verbally defined
   (Section 4).
3. An evaluation of nine ranking conditions, including the shipped ranker, a
   transcript-only ranker, and several fusion strategies, with an analysis of
   *why* the standard fusion methods underperform on this task and a
   normalisation fix that resolves it (Sections 5 and 6).
4. Two secondary findings about the frame index: temporal sampling density
   does not translate into top-1 accuracy, and near-uniform frames behave as
   hubs in the embedding space (Section 6).

All code, the query set, and the raw results are in the project repository
under `eval/`, and every number in this report can be regenerated with a single
command against the same public videos.

# Background and related work

**Contrastive vision–language embeddings.** CLIP [14] trains an image
encoder and a text encoder so that matching image–caption pairs have high
cosine similarity and mismatched pairs have low similarity. The resulting space
supports zero-shot classification and cross-modal retrieval without further
training. Scrubless uses OpenCLIP [6], an open re-implementation,
with the ViT-B/32 architecture trained on the LAION-2B subset of LAION-5B
[18, 2]. ViT-B/32 is the smallest of the standard CLIP
backbones; I chose it because it runs at acceptable speed on a CPU, a hard
constraint for a self-funded deployment.

**Video retrieval with CLIP.** Applying CLIP to video by encoding individual
frames is well studied. CLIP4Clip [11] showed that frame-level CLIP
features with simple temporal aggregation are a strong baseline for text-to-
video retrieval, and Portillo-Quintero et al. [13] showed that even
averaging frame embeddings without any fine-tuning is competitive. Those works
retrieve *whole clips* from a corpus. Scrubless retrieves *moments within one
video*, which is closer to the temporal grounding task defined by Charades-STA
[5] and ActivityNet Captions [8] and addressed by models such
as Moment-DETR [9]. Those models are trained on annotated
query–interval pairs; Scrubless has no training data and no training step, so
the relevant comparison is the zero-shot frame-level baseline rather than the
supervised state of the art.

**Speech and lexical retrieval.** Whisper [15] is a weakly supervised
speech-recognition model that produces segment-level timestamps, which is what
a moment retriever needs. Given a transcript, retrieving by spoken content is a
classical text-retrieval problem; BM25 [17] remains a strong
lexical baseline. Whisper is also known to hallucinate fluent text on silence
and music [7], a failure mode that appears in my data.

**Combining rankers.** Fusing rankings from heterogeneous retrievers has a long
history. CombSUM [4] adds normalised scores; reciprocal rank fusion
[3] adds transformed ranks and is popular precisely because it
needs no score normalisation. Both are used as-is in production "hybrid
search" systems. Section 6 examines why neither works well here without
modification.

**Hubness.** In high-dimensional spaces, a few points become nearest neighbours
of disproportionately many queries [16]. The phenomenon is known
to affect cross-modal CLIP retrieval, and it turns out to have a concrete,
visible cause in a frame index: fade-to-black frames.

# System design

## Constraints

Scrubless was built under a self-imposed rule of radical simplicity: one
language (Python), one process, no container orchestration, no build step for
the front end, and every external dependency optional. The rule exists because
the product had to be shippable by one person in days and runnable for a few
dollars a month. It also has a methodological benefit: the retrieval pipeline
is short enough to reproduce exactly in an offline evaluation script, which is
what Section 5 does.

## Pipeline

![System overview. One FastAPI process holds the CLIP model and the vector
database in memory; everything else is an external API call.](diagrams/architecture.pdf){width=78%}

**Indexing.** When a video is uploaded, a background thread runs the pipeline
in Figure 2. `ffmpeg` extracts one JPEG every $I = 5$ seconds (the
`FRAME_INTERVAL` constant) and a 16 kHz mono audio track. The audio is sent
to the Whisper API, which returns segments of the form $(t_{\text{start}},
t_{\text{end}}, \text{text})$. Each frame $i$ is assigned the window $[iI,
(i+1)I)$ and the concatenation of all transcript segments overlapping that
window. The frame is encoded by the CLIP image encoder and L2-normalised, and
the vector is written to a ChromaDB collection [1] together with the
metadata `{video_id, timestamp, frame_path, transcript_segment}`. ChromaDB
runs in-process and uses an HNSW index [12] with cosine distance.

![Indexing. Frames and audio are extracted in parallel, joined per 5-second
window, embedded, and stored.](diagrams/indexing.pdf){width=100%}

**Search.** A query is encoded by the CLIP text encoder, L2-normalised, and
submitted to ChromaDB, which returns the ten nearest frames restricted to the
requested video. The score shown to the user is $1 - d$, where $d$ is the
cosine distance. The top three results are additionally passed, with their
frame image, to a vision-capable language model that writes a one-sentence
description; this is a presentation aid and plays no role in ranking. The
front end renders the results as thumbnails; clicking one seeks the HTML5
player to the frame's timestamp.

![Search. The query is embedded into the same space as the frames and matched
by cosine similarity; the transcript is returned as a snippet but is not
scored.](diagrams/search.pdf){width=100%}

The point to notice is that the transcript participates in the *display* of a
result but not in its *retrieval*. This was a deliberate first-version choice:
the visual path worked end to end, and I did not want to combine two rankers
before I could measure either. The evaluation below is the measurement.

## Later additions

After the core loop worked, the system grew a library mode that indexes a
directory of videos and searches across them, question answering grounded in
the transcript with clickable timestamp citations, automatic chapter
generation, highlight-reel export, user accounts, and a billing tier. None of
these change the ranking function, and I do not evaluate them here. The
backend was later split from a single file into fourteen modules with a
one-way import graph; the `uvicorn app:app` entry point is unchanged.

\newpage

# Benchmark

The product had no ground truth of any kind, so building a benchmark was the
first task. I had three requirements: the videos must be openly licensed, so
that anyone can rerun the evaluation; they must differ in how much of their
content is visual versus spoken; and the queries must be the kind of thing a
real user would type, not captions reverse-engineered from the frames.

## Videos

Table: Evaluation videos. "Speech windows" is the share of 5-second windows
with any transcribed speech.

| id | title | duration | frames (5 s) | speech windows | licence |
|:---|:----------------------------------|------:|-----:|-----:|:---------|
| `tos` | *Tears of Steel* (Blender Foundation, 2012) | 12:14 | 147 | 55 % | CC BY 3.0 |
| `bbb` | *Big Buck Bunny* (Blender Foundation, 2008) | 9:56 | 119 | 0 % | CC BY 3.0 |
| `nasa` | *Dan Goes to Kazakhstan* (NASA Johnson, 2016) | 7:53 | 95 | 87 % | CC0 |

*Tears of Steel* is a live-action science-fiction short with dialogue and
distinctive visual set pieces. *Big Buck Bunny* is an animated film with a
music-only soundtrack: Whisper returns only a pair of musical-note glyphs, so it serves as a
control for what fusion does when the transcript channel carries no
information. The NASA video is a hand-held travelogue narrated to camera,
where most of what matters is said rather than shown. Together they span
30 minutes and 361 five-second windows. The files were fetched from the
Blender Foundation's and the Internet Archive's download servers, not from a
streaming site; the download URLs are recorded in `eval/run_eval.py`.

## Queries and ground truth

I wrote 65 queries. The 39 **visual** queries describe something that can be
seen ("a brain on a plate with needles stuck in it", "a flying squirrel gliding
through the air", "an astronaut being carried in a chair by the recovery
crew"). The 26 **spoken** queries describe something that is said. Seventeen of
those are near-verbatim ("you're a jerk, Tom"; "water, earplugs and the
satellite phone") and nine are **paraphrases** that share few or no content
words with the transcript ("he wishes he had brought warmer clothes" for *a
sweater would have been a good idea*; "why the landing site is flat and
empty"). The paraphrases exist to separate lexical matching from semantic
matching in the transcript channel.

Ground truth for each query is one or more time intervals. For visual queries
I labelled from timestamped contact sheets of the 5-second frames (Figure 4
shows one) and, where a shot spans several frames, from the frames on either
side. For spoken queries I labelled from the Whisper segment timestamps. A
query may have several intervals when the same content recurs; the sniper
query in *Tears of Steel*, for instance, has three. Nine of the 65 queries are
single-frame targets. Labels are stored in `eval/queries.json`.

![A contact sheet used for labelling: the 5-second frames of *Big Buck Bunny*
from 2:30 to 4:55, each stamped with its timestamp.](../eval/work/bbb/sheets/sheet_01.jpg){width=100%}

## Metrics

A returned timestamp $t$ is a hit for a query with intervals
$\{[s_j, e_j]\}$ if $s_j - \tau \le t \le e_j + \tau$ for some $j$, with
tolerance $\tau = 5$ s, one frame interval. Given the ranked list of the top
ten timestamps, I record the rank of the first hit and report **Recall@k** for
$k \in \{1, 5, 10\}$, the fraction of queries whose first hit is at rank
$\le k$, and **mean reciprocal rank** (MRR), the mean of $1/\text{rank}$ with
misses scored as zero. Recall@1 is the metric the product experience actually
depends on: a user clicks the first thumbnail. Recall@10 measures whether the
answer is on the page at all.

## Threats to validity

The benchmark is small (65 queries, three videos), and I wrote both the
queries and the labels, so the query phrasing reflects one person's habits.
The contact sheets I labelled from are the same 5-second frames the index is
built on, which favours no ranking condition over another but does mean a
sub-5-second event that falls between frames is invisible to both the labels
and the index. Whisper's segment timestamps, used for spoken-query labels, are
themselves approximate. I mitigate the first two concerns by reporting
per-video and per-query-type breakdowns, by validating the one tuned
parameter with leave-one-video-out selection, and by publishing the query
set. None of the numbers below should be read to more than about two
significant figures.

# Experimental setup

## Reproduction of the shipped ranker

The evaluation script does not call the running product; it re-implements
the pipeline offline so that alternative rankers can be compared on identical
inputs. The re-implementation loads the same OpenCLIP weights (`ViT-B-32`,
`laion2b_s34b_b79k`), runs the same `ffmpeg` command (`fps=1/5`), assigns the
same timestamps ($iI$ for frame $i$), uses the same transcript-window join,
and ranks by exact cosine similarity over the L2-normalised vectors. The only
difference from production is that ChromaDB's HNSW index is replaced by a
brute-force dot product; with at most 367 vectors per video the HNSW search is
exact at its default parameters, so the rankings are identical. Nothing in the
script touches the product's database.

## Ranking conditions

All conditions rank the frames of a single video for a single query and
return the top ten. Let $\mathbf{q}$ be the query embedding, $\mathbf{f}_i$
the embedding of frame $i$, and $d_i$ the transcript text of frame $i$'s
window.

* **Visual (shipped).** Score $v_i = \mathbf{q} \cdot \mathbf{f}_i$.
* **Visual, 2 s.** The same with $I = 2$ (367, 298, and 237 frames per video).
* **Visual, 2 s + NMS.** As above, then temporal non-maximum suppression:
  walking down the ranking, drop any frame within 5 s of an already-kept
  frame.
* **Transcript, CLIP.** Encode each $d_i$ with the CLIP *text* encoder and
  score $\mathbf{q} \cdot \mathbf{t}_i$; windows with no speech are excluded.
  This is the cheapest way to add the transcript to the existing index, since
  the vectors live in the same space.
* **Transcript, BM25.** Standard BM25 ($k_1 = 1.5$, $b = 0.75$) treating each
  window's text as a document; windows with zero score are excluded.
* **Hybrid, RRF.** Reciprocal rank fusion of the visual and BM25 rankings
  (top 50 of each, $k = 60$).
* **Hybrid, CombSUM (max-normalised).** $\alpha \, \tilde v_i + (1 - \alpha)
  \, b_i / \max_j b_j$, where $\tilde v_i$ is $v_i$ min–max-normalised over
  the video's frames and $b_i$ is the BM25 score. $\alpha = 0.5$.
* **Hybrid, CombSUM (coverage-normalised).** As above but with BM25 divided by
  $\sum_{w \in q} \mathrm{idf}(w)$, the score of an average-length document
  containing every query term exactly once. The quotient is an idf-weighted
  fraction of the query that the window covers. $\alpha = 0.5$.
* **Coverage + blank-frame suppression.** As above, additionally excluding any
  frame whose grey-level standard deviation is below 5 (a near-uniform
  frame).

Both CombSUM variants degrade to the visual ranker when no window has a
lexical match, which is the correct behaviour for the music-only control.
The α sweep and the leave-one-video-out selection in Section 6.3 examine the
single tunable parameter.

## Hardware and software

All timings are from a single machine: Apple M3 Pro, 18 GB of memory, no GPU
used. Python 3.10.9, PyTorch 2.2.2, OpenCLIP 3.3.0, ChromaDB 1.5.9, FFmpeg
8.1.1; Whisper is the hosted `whisper-1` API. CLIP inference runs on the CPU
in batches of 32.

# Results

## Main comparison

Table 2 reports the five-second-index conditions on the full benchmark and by
query type; Figure 5 shows the Recall@1 columns. Table 3 gives the per-video
breakdown.

Table: Retrieval quality on the 65-query benchmark, 5-second frame index.
Best value per column in bold.

| Condition | All R@1 | All R@5 | All R@10 | All MRR | Visual R@1 | Spoken R@1 |
|:----------------------------|------:|------:|------:|------:|------:|------:|
| Visual (shipped) | 0.51 | 0.66 | 0.78 | 0.581 | 0.77 | 0.12 |
| Transcript, CLIP | 0.42 | 0.66 | 0.74 | 0.510 | 0.18 | 0.77 |
| Transcript, BM25 | 0.42 | 0.49 | 0.57 | 0.451 | 0.10 | **0.88** |
| Hybrid, RRF | 0.43 | 0.82 | 0.88 | 0.596 | 0.41 | 0.46 |
| Hybrid, CombSUM max-norm | 0.58 | 0.82 | 0.92 | 0.687 | 0.38 | **0.88** |
| Hybrid, CombSUM coverage-norm | 0.78 | **0.92** | 0.94 | 0.843 | 0.77 | 0.81 |
| \ + blank-frame suppression | **0.80** | **0.92** | **0.95** | **0.853** | **0.79** | 0.81 |

![Recall@1 by condition and query type (5-second index).](assets/eval_conditions.pdf){width=100%}

Table: Per-video Recall@1 / MRR, 5-second index. *Big Buck Bunny* has no
speech, so the transcript-only ranker returns nothing and every hybrid
reduces to the visual ranker.

| Condition | *Tears of Steel* (23) | *Big Buck Bunny* (14) | NASA (28) |
|:--------------------------|------------:|------------:|------------:|
| Visual (shipped) | 0.48 / 0.504 | 0.50 / 0.639 | 0.54 / 0.615 |
| Transcript, BM25 | 0.48 / 0.532 | 0.00 / 0.000 | 0.57 / 0.611 |
| Hybrid, RRF | 0.39 / 0.561 | 0.50 / 0.639 | 0.43 / 0.602 |
| Hybrid, CombSUM max-norm | 0.52 / 0.635 | 0.50 / 0.639 | 0.68 / 0.753 |
| Hybrid, CombSUM coverage-norm | 0.87 / 0.898 | 0.50 / 0.639 | 0.86 / 0.900 |
| \ + blank-frame suppression | 0.87 / 0.902 | 0.50 / 0.639 | 0.89 / 0.920 |

Three things stand out.

First, the two single-channel rankers are almost perfectly complementary. The
shipped visual ranker puts the right frame first for 77 % of visual queries
and 12 % of spoken queries; BM25 over the transcript puts it first for 88 % of
spoken queries and 10 % of visual queries. Neither is a usable general-purpose
ranker on its own, and the shipped system is the visual one. On the NASA
video, whose content is mostly narration, the product as deployed answers
barely half of the queries correctly at rank 1.

Second, the standard fusions make the visual half *worse*. RRF lifts overall
Recall@10 to 0.88, which is why it looks attractive in aggregate, but drops
visual Recall@1 from 0.77 to 0.41 and only reaches 0.46 on spoken queries.
Max-normalised CombSUM keeps BM25's spoken accuracy but halves the visual
accuracy (0.38). A hybrid that trades the product's existing strength for its
missing one is not an improvement.

Third, changing only the normalisation of the lexical score resolves this.
Coverage-normalised CombSUM at the untuned default $\alpha = 0.5$ matches the
visual ranker on visual queries (0.77) and comes within seven points of BM25
on spoken queries (0.81), for an overall Recall@1 of 0.78 and MRR of 0.843. On
the music-only control it is, by construction, identical to the visual ranker.
Suppressing blank frames adds two points on the visual side. The final
configuration reaches Recall@1 = 0.80, Recall@5 = 0.92, Recall@10 = 0.95, and
MRR = 0.853, and requires no new model, no training, and no additional
index: the transcript text is already stored per window.

## Transcript channel: embeddings versus lexical matching

Table 4 splits the spoken queries into verbatim and paraphrased.

Table: Spoken queries by phrasing (Recall@1 / MRR).

| Condition | Verbatim (17) | Paraphrase (9) |
|:--------------------------|------------:|------------:|
| Visual (shipped) | 0.06 / 0.168 | 0.22 / 0.291 |
| Transcript, CLIP | 0.88 / 0.931 | 0.56 / 0.596 |
| Transcript, BM25 | 1.00 / 1.000 | 0.67 / 0.704 |
| Hybrid, coverage-norm | 0.88 / 0.941 | 0.67 / 0.705 |

BM25 is perfect on verbatim queries, as expected. The more interesting row is
CLIP's text encoder used as a text–text retriever, which trails BM25 on
*both* subsets, including the paraphrases where a semantic encoder should have
the advantage. CLIP's text tower is trained only to align with images, not
with other text, and the modality gap in contrastive models [10] means
text–text cosine similarity is not well calibrated. It also has a 77-token
input limit that would truncate longer windows. A sentence-embedding model
trained on text pairs would be the principled choice for paraphrase; I did
not add one because it would be a second model to ship, and because
BM25 already covers two-thirds of the paraphrases through incidental shared
terms ("Kazakhstan", "Norway", "time zones").

## Sensitivity to the fusion weight

Figure 6 sweeps $\alpha$ for both CombSUM variants. With max-normalisation
there is no good value: every $\alpha$ sacrifices one query type. With
coverage-normalisation the two curves cross near $\alpha = 0.5$, and visual
accuracy is flat from 0.4 upward, so the default is also close to the optimum.
To check that this is not tuning on the test set, I selected $\alpha$ by
maximising MRR on two videos and evaluated on the third (Table 5). The pooled
held-out result, Recall@1 = 0.77 and MRR = 0.837, is within one point of the
in-sample number.

![Recall@1 as a function of the visual weight $\alpha$, for the two
normalisations of the BM25 score. Dashed line: the default
$\alpha = 0.5$.](assets/eval_alpha.pdf){width=100%}

Table: Leave-one-video-out selection of $\alpha$ (coverage-normalised
fusion, 5-second index).

| Held-out video | $\alpha$ chosen on the other two | n | R@1 | R@5 | R@10 | MRR |
|:------------------|------------:|---:|-----:|-----:|-----:|------:|
| *Tears of Steel* | 0.5 | 23 | 0.87 | 0.91 | 0.96 | 0.898 |
| *Big Buck Bunny* | 0.4 | 14 | 0.50 | 0.86 | 0.86 | 0.639 |
| NASA | 0.4 | 28 | 0.82 | 0.96 | 0.96 | 0.887 |
| Pooled | — | 65 | 0.77 | 0.92 | 0.94 | 0.837 |

## Frame sampling density

Table 6 compares the 5-second index with a 2-second index, with and without
temporal non-maximum suppression, on the visual queries where sampling density
could plausibly matter.

Table: Effect of frame interval on visual queries (n = 39).

| Condition | R@1 | R@5 | R@10 | MRR | frames / video |
|:------------------------|-----:|-----:|-----:|------:|---------:|
| Visual, 5 s | 0.77 | 0.92 | 0.92 | 0.828 | 95–147 |
| Visual, 2 s | 0.67 | 0.87 | 0.95 | 0.769 | 237–367 |
| Visual, 2 s + NMS (5 s) | 0.67 | 0.90 | 0.97 | 0.775 | 237–367 |

Sampling 2.5× more frames costs 2.5× the CLIP compute and *lowers* Recall@1
by ten points. Part of the loss is crowding: a correct shot now occupies
several adjacent slots in the top ten, pushing other candidates off the page,
and suppression recovers the Recall@10 (0.95 → 0.97). But suppression does not
recover Recall@1, so crowding is not the main effect. The more likely
explanation is that denser sampling gives every *incorrect* shot more draws
from its distribution of frame embeddings, and the maximum over more draws is
larger; a wrong shot's single best frame is more likely to edge out the right
shot's best frame. At the product's five-second default the trade-off is
already on the right side, and I did not pursue finer sampling.

## Hubs

Some frames appear in the top ten for many unrelated queries. Counting, for
each video, how often each frame is retrieved across that video's visual
queries reveals a specific culprit: the fully black frames. The two black
frames in the NASA video (fade-outs at 7:15 and 7:45) are in the top ten for
five of its fourteen visual queries, and the black final frame of *Tears of
Steel* appears in four of eleven; each has a grey-level standard deviation of
exactly zero. A uniform image has an embedding that sits near the centre of
the image distribution and is therefore moderately similar to everything, the
textbook hub of Radovanović et al. [16]. One of them ranked
first for "a man talking on a mobile phone". Discarding frames with grey-level
standard deviation below 5 removes three frames from the 361 and raises visual
Recall@1 from 0.77 to 0.79 and Recall@10 from 0.92 to 0.95. The check costs
one array operation per frame at index time.

## Cost

Table 7 gives the indexing cost per condition for the 30 minutes of video, and
the query-time cost.

Table: Resource cost. CLIP on an M3 Pro CPU; Whisper via API.

| Stage | Total for 30 min of video | Per minute of video |
|:----------------------------------------|----------------:|--------------:|
| Frame extraction, `ffmpeg`, 5 s | 7.0 s | 0.23 s |
| CLIP image encoding, 5 s (361 frames) | 21.3 s | 0.71 s |
| CLIP image encoding, 2 s (902 frames) | 38.3 s | 1.28 s |
| Whisper transcription (API round trip) | 50.9 s | 1.70 s |
| CLIP text encoding of transcript windows, 5 s | 14.3 s | 0.48 s |

At query time the CLIP text encoder takes 56 ms (median, warm) and the
brute-force similarity over one video's frames takes under 0.1 ms. BM25 over
the same windows is of the same order. The hybrid therefore adds nothing
perceptible to the roughly 60 ms search latency; the vision-language
description of the top three results, which the product performs after
ranking, dominates the user-visible time at one to two seconds.

# Discussion

**What the shipped ranker gets wrong.** Of the nine visual queries that the
visual ranker does not place first, three are outright misses that no
condition recovers. "The movie title card" returns other text-on-black cards (the
"Blender Foundation presents" and end-credit frames) ahead of the actual title;
CLIP reads text in images, and every card is a plausible match. "A big white
rabbit coming out of its burrow" fails because the burrow shots are dark and
the rabbit is small in frame; the ranker prefers well-lit frames where the
rabbit fills the image. "The rabbit standing proudly with its chest out" is a
pose description, which ViT-B/32 does not capture. The remaining near-misses
(rank 2–5) are all cases where a *similar* shot outranks the labelled one, for
instance a different flying-squirrel shot from the one I labelled first.

**Why fusion fails without calibration.** The two channels' scores mean
different things. A CLIP cosine similarity is bounded and its top value for a
video is typically around 0.3 (median 0.29, maximum 0.39 on this benchmark), but the *gap* between the best and the next frame
is what carries information, and min–max normalisation preserves that. A BM25
score is unbounded and query-dependent: a two-term query over 5-second windows
might produce a top score of 1.5 when only one common word matches, or of 9
when both rare words do. Normalising by the observed maximum maps both cases
to 1.0, so a visual query that happens to share the word "man" with one window
hands that window half of its fused score. Reciprocal rank fusion discards
scores entirely and so cannot distinguish a confident lexical hit from a
spurious one at all, which is why it does worst on both query types. The
coverage normaliser asks a different question, "what fraction of this query's
information does the window contain?", and a one-common-word match answers
"very little". This is a small change with a large effect, and it generalises:
any fused lexical score should be normalised against what the query *could*
have scored, not against what it *did* score.

**What the evaluation does not show.** Spoken-query performance depends
entirely on transcript quality. The NASA video is clean narration; a noisy
recording of a meeting with overlapping speakers would degrade both Whisper and
everything downstream. Whisper's hallucinations are visible even here: on the
music-only ending of *Tears of Steel* it emitted "No!" eleven times at
30-second intervals, and on the crew's chatter it emitted a run of "You." on
one-second segments. These did not affect any labelled query, but a user
searching for "no" would land in the credits. The blank-frame threshold and
the BM25 parameters are defaults, not tuned values, and the α selection is the
only place I fit anything. The benchmark contains no queries that combine
both channels ("the part where the old man talks about passion while looking
at the brain"), which is where fusion should shine and where I have no
evidence either way.

**Implications for the product.** The result argues for shipping the
coverage-normalised hybrid as the default ranker. It is a change of about
thirty lines: compute BM25 over the windows already stored in the vector
database's metadata, normalise, and add. It changes no schema, adds no
service, and, on the evidence here, roughly doubles the fraction of spoken
queries answered at rank 1 while leaving visual queries untouched. Blank-frame
suppression is a one-line filter at index time. Denser sampling should not be
adopted without a shot-level aggregation step, which the results suggest is
the actual missing piece.

# Conclusion

I built a moment-retrieval system around a zero-shot vision–language
embedding, deployed it, and then measured it. The measurement showed that the
system worked for the queries I had imagined when designing it and did not
work for a large class of queries users actually type, those about what was
said. It also showed that the textbook fix, rank fusion with a lexical
retriever, damages the part that already worked, and that the damage comes
from a normalisation choice rather than from fusion itself. Normalising the
lexical score by query coverage gives a ranker that is at least as good as
either channel alone on that channel's queries, at no cost in latency or
infrastructure, and holds up under leave-one-video-out validation.

Two directions follow. The first is aggregation: treating shots rather than
frames as the unit of retrieval, which would let the index sample more densely
without the top-1 penalty I measured and would give a natural place to combine
visual and spoken evidence over a span longer than five seconds. The second is
a proper semantic text channel: a sentence encoder for the transcript, which
would address the paraphrase queries that BM25 reaches only by luck. Both
should be evaluated on a larger benchmark than this one, with queries written
by people other than the system's author, and ideally with the compound
queries that this benchmark lacks.

\newpage

# References

[1] Chroma. *Chroma: the open-source embedding database.*
https://github.com/chroma-core/chroma, 2023.

[2] M. Cherti, R. Beaumont, R. Wightman, M. Wortsman, G. Ilharco,
C. Gordon, C. Schuhmann, L. Schmidt, and J. Jitsev. Reproducible scaling laws
for contrastive language-image learning. In *Proc. CVPR*, 2023.

[3] G. V. Cormack, C. L. A. Clarke, and S. Büttcher. Reciprocal
rank fusion outperforms Condorcet and individual rank learning methods. In
*Proc. SIGIR*, pages 758–759, 2009.

[4] E. A. Fox and J. A. Shaw. Combination of multiple searches. In
*Proc. TREC-2*, NIST Special Publication 500-215, pages 243–252, 1994.

[5] J. Gao, C. Sun, Z. Yang, and R. Nevatia. TALL: Temporal activity
localization via language query. In *Proc. ICCV*, 2017.

[6] G. Ilharco, M. Wortsman, R. Wightman, C. Gordon, N. Carlini,
R. Taori, A. Dave, V. Shankar, H. Namkoong, J. Miller, H. Hajishirzi,
A. Farhadi, and L. Schmidt. OpenCLIP. Zenodo, 2021.
doi:10.5281/zenodo.5143773.

[7] A. Koenecke, A. S. G. Choi, K. X. Mei, H. Schellmann, and
M. Sloane. Careless Whisper: Speech-to-text hallucination harms. In *Proc.
ACM FAccT*, 2024.

[8] R. Krishna, K. Hata, F. Ren, L. Fei-Fei, and J. C. Niebles.
Dense-captioning events in videos. In *Proc. ICCV*, 2017.

[9] J. Lei, T. L. Berg, and M. Bansal. Detecting moments and highlights
in videos via natural language queries. In *Advances in Neural Information
Processing Systems 34*, 2021.

[10] W. Liang, Y. Zhang, Y. Kwon, S. Yeung, and J. Zou. Mind the gap:
Understanding the modality gap in multi-modal contrastive representation
learning. In *Advances in Neural Information Processing Systems 35*, 2022.

[11] H. Luo, L. Ji, M. Zhong, Y. Chen, W. Lei, N. Duan, and T. Li.
CLIP4Clip: An empirical study of CLIP for end to end video clip retrieval and
captioning. *Neurocomputing*, 508:293–304, 2022.

[12] Y. A. Malkov and D. A. Yashunin. Efficient and robust
approximate nearest neighbor search using Hierarchical Navigable Small World
graphs. *IEEE Trans. Pattern Analysis and Machine Intelligence*,
42(4):824–836, 2020.

[13] J. A. Portillo-Quintero, J. C. Ortiz-Bayliss, and
H. Terashima-Marín. A straightforward framework for video retrieval using
CLIP. In *Proc. Mexican Conference on Pattern Recognition (MCPR)*, 2021.

[14] A. Radford, J. W. Kim, C. Hallacy, A. Ramesh, G. Goh,
S. Agarwal, G. Sastry, A. Askell, P. Mishkin, J. Clark, G. Krueger, and
I. Sutskever. Learning transferable visual models from natural language
supervision. In *Proc. ICML*, 2021.

[15] A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, and
I. Sutskever. Robust speech recognition via large-scale weak supervision. In
*Proc. ICML*, 2023.

[16] M. Radovanović, A. Nanopoulos, and M. Ivanović. Hubs in
space: Popular nearest neighbors in high-dimensional data. *Journal of
Machine Learning Research*, 11:2487–2531, 2010.

[17] S. Robertson and H. Zaragoza. The probabilistic relevance
framework: BM25 and beyond. *Foundations and Trends in Information
Retrieval*, 3(4):333–389, 2009.

[18] C. Schuhmann, R. Beaumont, R. Vencu, C. Gordon, R. Wightman,
M. Cherti, T. Coombes, A. Katta, C. Mullis, M. Wortsman, P. Schramowski,
S. Kundurthy, K. Crowson, L. Schmidt, R. Kaczmarczyk, and J. Jitsev. LAION-5B:
An open large-scale dataset for training next generation image-text models.
In *Advances in Neural Information Processing Systems 35*, Datasets and
Benchmarks Track, 2022.


\newpage

# Appendix: reproducing the evaluation

```bash
# from the repository root, with OPENAI_API_KEY set in .env
.venv/bin/python eval/run_eval.py --selftest   # metric unit checks
.venv/bin/python eval/run_eval.py index        # frames, audio, Whisper, CLIP (cached)
.venv/bin/python eval/run_eval.py sheets       # contact sheets used for labelling
.venv/bin/python eval/run_eval.py score        # all conditions -> eval/results/
.venv/bin/python eval/make_figures.py          # figures 5 and 6
```

The three videos are downloaded into `eval/data/` from the URLs in
`eval/run_eval.py`. `eval/queries.json` holds the 65 queries with ground
truth; `eval/results/per_query.json` holds the top-5 timestamps and first-hit
rank for every query under every condition, and `eval/results/summary.json`
the aggregates in the tables above.
