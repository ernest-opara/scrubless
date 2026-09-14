# Scrubless Pivot Analysis — June 2026

**Author:** Architecture & strategy notes prepared for the YC Summer 2026 application window (deadline 2026-07-27).

**Premise.** Scrubless today is a working semantic-video-search consumer app at getscrubless.com. The core ML pipeline (CLIP frame embeddings, Whisper transcription, ChromaDB retrieval, Claude Vision enrichment, citation-back-to-timestamp) is the *engine*, not the *product*. This document evaluates 10 pivot directions where the existing engine becomes the unfair advantage for a company that pattern-matches what YC has been funding.

---

## Part I — The market signal: YC's Summer 2026 RFS

The Requests for Startups list is YC explicitly telling founders what they want to fund. The Summer 2026 list (16 categories) is heavily weighted toward four themes:

| Theme | RFS lines |
|---|---|
| **Agent infrastructure** | Software for Agents · Inference Chips for Agent Workflows · AI Operating System for Companies · Dynamic Software Interfaces |
| **AI-native replacement of legacy work** | AI-Native Service Companies · SaaS Challengers · AI-Native Discovery Engines |
| **Enterprise / institutional buyers** | Sell to F100 · Company Brain |
| **Hardware / dynamism** | Counter-Swarm Defense · Hardware Supply Chain · Electronics in Space · Industrial Capabilities in Space · Supply Chain 2.0 for Semiconductors · AI Personalized Medicine · AI for Low-Pesticide Agriculture |

The first three buckets are software plays a video-understanding engine could plausibly extend into. The hardware bucket is off-thesis for Scrubless's existing IP — ignore.

## Part II — Pattern across the last 8 YC batches

Tracking observable funding patterns batch-over-batch (W23 → W26):

- **W23, S23**: GPT-3.5/4 wave. Lots of horizontal "AI for X" wrappers. Many funded; most didn't survive because the moat was a prompt.
- **W24**: Vertical AI thesis crystallises (Harvey-style legal, Decagon-style support, Crosby-style ops). Agent shells still considered "research demos."
- **S24**: First wave of multimodal startups (vision agents, voice agents). YC starts funding agent infra explicitly.
- **W25**: AI infra batch — Modal, Together, Anyscale, Baseten, Replicate-likes funded in clusters. Cursor-wave AI-native rewrites pattern emerges.
- **S25**: "Cursor for X" wave matures. SaaS-replacement plays in design, code, sales, ops. Agents move from research to product.
- **W26 (current)**: Multimodal agents, voice AI dominate. "Software for Agents" RFS emerges as its own category. F100 buyer thesis hardens.

**The trendline is clear**: in 2026 YC funds (a) infrastructure agents will consume, (b) AI-native services that replace human-staffed industries, and (c) tools that turn enterprises into queryable, agent-readable assets.

What did NOT survive the screening: consumer creator tools without proven retention, "Notion for X" plays, ML SaaS with prompt-only moats.

## Part III — The 10 pivots

Each section: pitch · architecture · how it works · what survives from Scrubless · how it transitions · why-now · risk.

---

### 1. Stripe for Video — Video Understanding as a Developer API

**Pitch.** Every product with video in it (Notion, Loom, Slack, Linear, Zendesk, ServiceNow, Salesforce, Bubble, vertical SaaS) wants semantic search, Ask, and citations over that video. None will build the embedding/retrieval stack themselves. We sell the API.

**Architecture.**
```
[Customer App]                       [Scrubless API]
     │  POST /v1/videos (URL or file)         │
     ├─────────────────────────────────────────►  Ingest queue → CLIP + Whisper workers
     │  webhook(indexed)                       │  ChromaDB tenant-scoped collection
     │ ◄────────────────────────────────────────  Per-project isolation
     │  POST /v1/search {query, project_id}    │
     ├─────────────────────────────────────────►  Vector search + Claude Vision enrichment
     │  ◄  [{timestamp, score, frame_url, ...}]│
     │  POST /v1/ask {question, project_id}    │
     ├─────────────────────────────────────────►  RAG over transcript + frames → cited answer
     │  ◄  {answer, citations: [{vid_id, t}]}  │
```

Three new layers on top of today's Scrubless: (a) **API-key + project_id** tenant isolation, (b) **async ingest jobs + webhooks**, (c) **per-key usage metering for billing** (already have the Event table).

**Scrubless reuse.** ~90%. Endpoints become public API. Consumer UI becomes the live demo.

**Transition.** 6 weeks of focused work. The hardest piece — multi-tenant security under load — must be adversarially tested.

**RFS map.** "Software for Agents" (the canonical buyer), "SaaS Challengers" (adjacent).

**Why now.** Agents need to read video the same way they read text and APIs. Nobody has shipped this primitive.

**Risk.** OpenAI / Anthropic could ship something equivalent free in 18 months. Defence: proprietary retrieval pipeline + cheaper than per-frame GPT-4V calls + open-weight CLIP gives a cost moat.

---

### 2. AI-Native Video Editor — "Cursor for Premiere"

**Pitch.** Adobe is asleep on AI-native. Describe the cut you want ("3-min highlight, hero shot first, drop the stumbles, end on a laugh") and an agent assembles a draft from your footage with every cut citing a timestamp. The first AI-native NLE wins a $30B+ market.

**Architecture.**
```
Raw footage  → Scrubless engine (indexed segments + visual + audio embeddings)
                                          │
User prompt  → Planning agent ───────────►│ retrieve candidate moments per brief beat
                                          │ score by relevance + diversity
                                          │ assemble timeline JSON
                                          ▼
                            FFmpeg cut pipeline (existing reels.py extended)
                                          │
                                          ▼
                            Web-native timeline UI (React or Remotion)
                                          │
                                          ▼
                            Export → MP4 / Premiere XML / Resolve EDL / FCPXML
```

**Scrubless reuse.** ~75%. The engine, the reel-stitching ffmpeg pipeline, the citation primitive. New build: the timeline UI, the agent loop that converts prompts into edit plans, the NLE-format exporters.

**Transition.** 10–14 weeks for a YC-quality demo. Too tight for July 27.

**RFS map.** "SaaS Challengers" (textbook fit).

**Why now.** GPT-5-class models can plan multi-step creative tasks. Adobe Premiere is a 30-year codebase. Descript is the only credible startup competitor and they pre-date the agent wave.

**Risk.** UX bar is brutal. Editors are opinionated. Adobe will move within 12 months once they see traction. Bigger swing, bigger payoff.

---

### 3. Video Watcher Agents — Always-On Multimodal Monitors

**Pitch.** An agent watches video so humans don't have to. Hedge fund agent monitors earnings calls and flags CFO uncertainty. Compliance agent watches every sales call and files SOX-relevant findings. Journalism agent monitors city council livestreams and pings on zoning topics. Wedge an ICP, replicate.

**Architecture.**
```
Live stream  ───► RTMP/HLS ingest worker ───► chunked frames + ASR
Recorded     ───► Scrubless engine                │
                                                   ▼
                            Continuous embedding stream → vector index
                                                   │
                                Subscription rules ◄┘
                                (DSL: "alert when CFO mentions guidance" or
                                 "find rooms where customer mentions churn")
                                          │
                                          ▼
                                Agent loop:
                                   - retrieves candidate moments
                                   - LLM judges signal strength
                                   - emits webhook / Slack / email
                                   - cites timestamps
```

**Scrubless reuse.** ~60%. Embedding/retrieval/citation reused. New: live-stream ingest, subscription rules engine, agent loop with judging, notification fan-out.

**Transition.** 8 weeks to MVP for one vertical (pick hedge funds first — they pay).

**RFS map.** "Software for Agents" (this IS the agent), "AI-Native Service Companies" (sold as monitoring service).

**Why now.** Multimodal models can finally watch + reason. Hedge funds already pay $$/seat for sentiment APIs over text — they have zero coverage on video.

**Risk.** ICP discipline. Diffuse buyer kills this. Must pick one.

---

### 4. Company Brain for Video — Maps Directly to YC RFS

**Pitch.** Every meeting recording, every sales call, every all-hands, every product demo, every Slack huddle becomes part of the company's *executable* knowledge graph. The CEO's strategy from the Q2 all-hands becomes a callable function the support agent uses to answer customer questions on brand. Maps verbatim to YC's "Company Brain" RFS line.

**Architecture.**
```
Sources: Zoom + Meet + Teams + Loom + Granola + uploaded recordings
           │
           ▼
Scrubless ingest → per-org video corpus
           │
           ▼
Knowledge extraction layer:
   - speakers identified (diarisation)
   - topics/entities extracted per moment
   - decisions/commitments tagged
   - cross-references built (this meeting referenced that doc)
           │
           ▼
Skills file: JSON contract per topic
   { "topic": "Q3 pricing change",
     "ground_truth_videos": [{vid, t_start, t_end}, ...],
     "current_position": "We're moving from per-seat to per-workspace",
     "decision_made_by": "CEO, 2026-04-12",
     "exceptions": [...] }
           │
           ▼
Agent API: ask("what's our position on X?") → answer + video citations
```

**Scrubless reuse.** ~65%. Engine + Ask + citations transfer. New: meeting bot infrastructure, diarisation, knowledge extraction layer, the "skills file" abstraction.

**Transition.** 10 weeks to MVP. Need Zoom OAuth, Meet/Teams bot, diarisation (Whisper-X or pyannote), entity extraction.

**RFS map.** **"Company Brain" — verbatim.** Also "AI Operating System for Companies."

**Why now.** Every white-collar company has 100x more recorded video than written knowledge — and zero way to query it semantically.

**Risk.** Enterprise sales cycle. But "Company Brain" being an explicit RFS line means YC is *actively looking* for this pitch.

---

### 5. AI-Native Compliance Service for Recorded Calls

**Pitch.** Replace the compliance analyst, not the QA tool. We ingest every recorded sales/support/healthcare call, generate the QA scores, file the regulatory reports, flag the violations, deliver the audit pack. Customers pay for the outcome (compliant calls, no fines), not the software. Direct fit for "AI-Native Service Companies" RFS.

**Architecture.**
```
Customer's call recording sink (Five9, Twilio, Genesys, Salesforce)
           │
           ▼
Scrubless ingest → indexed corpus per customer
           │
           ▼
Per-jurisdiction rule packs (TCPA, HIPAA, MiFID II, SOX, PCI, FCA conduct)
           │
           ▼
Continuous compliance agent: 
   - listens to every new call
   - runs each rule (e.g., "agent must offer recording disclosure within 10s")
   - flags violations with timestamped citations
   - generates auditor-ready PDF reports
           │
           ▼
Human-in-the-loop dashboard for edge cases
           │
           ▼
Monthly bill = per-call-hour processed + per-incident remediation
```

**Scrubless reuse.** ~70%. Engine + Ask. New: rule DSL, jurisdiction rule packs, dashboard, regulator-format exports.

**Transition.** 12 weeks to MVP. Need to pick one vertical/regulator pair first (TCPA for outbound sales is easiest entry).

**RFS map.** **"AI-Native Service Companies" — textbook fit.**

**Why now.** Compliance costs are exploding; head-count answer is broken; LLMs can finally read structured guidance and apply it consistently.

**Risk.** Selling to compliance officers is slow but they have budget. ACV $50K–$500K per customer.

---

### 6. AI-Native Discovery Engine for Recorded Media

**Pitch.** Scientists, journalists, policy researchers, lawyers all sit on massive corpora of recorded interviews, depositions, footage, hearings, podcasts, lectures — and they can't run anything but keyword search across them. We build an autonomous discovery agent that runs hypotheses across these corpora and surfaces patterns. Maps to "AI-Native Discovery Engines" RFS.

**Architecture.**
```
Corpus uploaded once (10K hours of bodycam, depositions, interviews, whatever)
           │
           ▼
Scrubless indexes everything (frames + audio + transcript + speakers + entities)
           │
           ▼
Researcher: "Find every time officer used force after a specific phrase was said"
           │
           ▼
Discovery agent:
   - decomposes hypothesis into searchable sub-queries
   - runs each sub-query against the index
   - cross-references results
   - finds correlations the researcher didn't ask for
   - delivers a report with cited examples + suggested follow-up hypotheses
```

**Scrubless reuse.** ~70%. Engine + Ask + citations. New: hypothesis decomposition agent, cross-reference engine, report generation.

**Transition.** 10 weeks for a single vertical.

**RFS map.** **"AI-Native Discovery Engines"** (verbatim).

**Why now.** Investigative journalism is collapsing. Academic research has too much data and not enough hands. Lawyers are buried in video evidence. Same primitive serves all three.

**Risk.** Each vertical wants different things. Pick one (journalism is easiest entry; legal is highest ACV).

---

### 7. AI-Native eDiscovery for Video

**Pitch.** Existing eDiscovery (Relativity, Everlaw, Logikcull) is text-first and terrible at video. Every modern lawsuit involves Zoom recordings, bodycam, depositions, security cam. Federal/AmLaw 100 contracts run $500K–$5M ARR. Slow sales but absurd ACV per logo.

**Architecture.**
```
Litigation hold → encrypted ingest → Scrubless engine
                       │
                       ▼
              Chain-of-custody log (immutable)
                       │
                       ▼
              Privilege detection (segments flagged as attorney-client)
                       │
                       ▼
              Issue tagging (matter-specific taxonomies)
                       │
                       ▼
              Discovery agent: "every reference to product X across all custodian recordings"
                       │
                       ▼
              Production export (FRCP-compliant, with Bates numbers)
```

**Scrubless reuse.** ~50%. Engine reused. New: chain-of-custody, privilege detection, audit logs, FRCP-format export, SOC2, on-prem option.

**Transition.** 16+ weeks. Not YC-velocity-friendly.

**RFS map.** "AI-Native Service Companies" (peripheral).

**Why now.** Federal courts increasingly demand video discovery. Existing tools haven't adapted.

**Risk.** Sales cycle. YC pattern-mismatch on speed of growth.

---

### 8. Dynamic Video Workflows — Forward-Deployed Engineer Tool

**Pitch.** A media/legal/medical operator types "ingest the videos in this S3 bucket, find every moment X happens, generate a report with thumbnails for each, email it to my team weekly" — and the system builds and runs that pipeline without code. Maps to YC's "Dynamic Software Interfaces" RFS.

**Architecture.**
```
User prompt ─► Pipeline planner agent ─► DAG over Scrubless primitives:
                                              [ingest] → [search] → [filter] → [format] → [deliver]
                                                                                   │
                                                                                   ▼
                                                        Scheduled execution (cron or webhook)
```

Each primitive is an existing Scrubless endpoint. The system is essentially Zapier/n8n × Scrubless engine, with a planner agent that writes the DAG from natural language.

**Scrubless reuse.** ~80%. Endpoints become tools. New: planner agent, DAG executor, scheduler, integrations (S3, Drive, email, Slack).

**Transition.** 8 weeks to MVP. Tight but doable.

**RFS map.** **"Dynamic Software Interfaces"** (verbatim). Also "Software for Agents."

**Why now.** Every domain expert can describe their workflow in English; nobody wants to learn a new no-code tool's UI.

**Risk.** Horizontal tools struggle to find ICP. Pick one workflow type first.

---

### 9. F100 Video Intelligence Suite

**Pitch.** Sell to the Fortune 100 enterprise: every all-hands, every customer call, every product demo, every training video across the org is queryable, askable, summarisable. One contract, multi-million ARR, multi-year. Maps to YC's "Sell to F100" RFS.

**Architecture.**
```
Enterprise sources:
  - Zoom Phone / Webex / Teams recordings
  - Workday Learning / Cornerstone training videos
  - Existing video archives (S3, SharePoint, Box)
           │
           ▼
Scrubless engine deployed in customer VPC (BYOC option)
           │
           ▼
SSO + role-based access (which exec sees which corpus)
           │
           ▼
Search + Ask + clip-share inside Slack/Teams/SharePoint
           │
           ▼
Audit logs + retention policy + region pinning + GDPR/SOC2
```

**Scrubless reuse.** ~65%. Engine reused. New: BYOC deployment, SSO, RBAC, enterprise integrations, audit/retention controls.

**Transition.** 14+ weeks. Then 6–12 months to first signed contract. Solo founder needs a CRO-quality co-founder.

**RFS map.** **"Sell to F100"** (verbatim).

**Why now.** F100 CTOs have a mandate to inject AI; "we have a video archive nobody can search" is a recognised gap.

**Risk.** Enterprise sales without an enterprise founder is a multi-year slog. Probably not the right play unless paired with a co-founder.

---

### 10. Real-Time Agent Hub for Live Broadcasts

**Pitch.** Subscribe agents to live financial broadcasts (CNBC, Bloomberg TV), congressional hearings, sports broadcasts, press conferences. Each agent watches in real time and emits structured signals — sentiment shifts, regulatory mentions, key plays, breaking news. Sell to trading firms, government affairs teams, sportsbooks.

**Architecture.**
```
24/7 stream ingest farm (HLS/RTMP) ─► continuous frames + ASR (live Whisper)
                                              │
                                              ▼
                              Streaming embedding index (rolling window)
                                              │
                                  Subscriber agents:
                                     - "alert when Fed mentions rate cut"
                                     - "alert when QB shows injury signs"
                                     - "alert when CEO contradicts prior statement"
                                              │
                                              ▼
                              Webhooks / Slack / Bloomberg terminals / API
```

**Scrubless reuse.** ~55%. Engine + Ask. New: live stream ingest at scale, low-latency streaming index, agent subscription model.

**Transition.** 12+ weeks. Capital-intensive (GPU costs for continuous live processing).

**RFS map.** "Software for Agents" + "Sell to F100" (trading desks).

**Why now.** Trading firms pay $$$ for ms-level information advantages. Vision/audio in live broadcast is currently zero-coverage.

**Risk.** Real-time GPU costs. Customer concentration in finance.

---

## Part IV — Scoring matrix

Seven factors, weighted. Scores 1–10. Weighted total / 100.

| # | Pivot | YC fit ×2 | TAM ×1.5 | Speed to MVP ×1.5 | Moat ×1 | Solo-feasible ×1 | Wedge clarity ×1 | Capital eff ×1 | **Total** |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Stripe for Video (API)** | 9 (18) | 9 (13.5) | 9 (13.5) | 7 | 8 | 9 | 9 | **78** |
| 4 | **Company Brain for Video** | 10 (20) | 9 (13.5) | 5 (7.5) | 9 | 5 | 8 | 6 | **69** |
| 8 | **Dynamic Video Workflows** | 9 (18) | 7 (10.5) | 7 (10.5) | 6 | 7 | 6 | 8 | **66** |
| 3 | **Watcher Agents** | 8 (16) | 8 (12) | 6 (9) | 7 | 7 | 7 | 7 | **65** |
| 5 | **AI-Native Compliance Service** | 9 (18) | 8 (12) | 4 (6) | 9 | 4 | 8 | 6 | **63** |
| 6 | **AI-Native Discovery Engine** | 8 (16) | 7 (10.5) | 5 (7.5) | 8 | 6 | 6 | 7 | **61** |
| 2 | **AI-Native Video Editor** | 7 (14) | 10 (15) | 3 (4.5) | 7 | 4 | 8 | 6 | **58.5** |
| 10 | **Live Broadcast Agent Hub** | 7 (14) | 7 (10.5) | 3 (4.5) | 8 | 4 | 7 | 4 | **49** |
| 9 | **F100 Video Intelligence** | 7 (14) | 10 (15) | 2 (3) | 7 | 2 | 6 | 4 | **51** |
| 7 | **AI-Native eDiscovery** | 6 (12) | 9 (13.5) | 2 (3) | 9 | 2 | 7 | 4 | **50.5** |
| — | *Scrubless as-is (baseline)* | *3 (6)* | *4 (6)* | *10 (15)* | *5* | *9* | *5* | *7* | **53** |

## Part V — Rankings

**Tier 1 — pitch this for YC Summer 2026 (deadline July 27):**

1. **Stripe for Video (#1)** — highest total. Hits the "Software for Agents" RFS dead-on. 6-week MVP is realistic. Scrubless code becomes the engine, consumer site becomes the demo. Solo-founder feasible. Cleanest pitch.

**Tier 2 — strong YC fit but tighter timeline / harder pitch:**

2. **Company Brain for Video (#4)** — maps to a literal RFS line called "Company Brain." Best moat, biggest YC partner appetite. But meeting-bot infrastructure (Zoom/Meet/Teams OAuth + diarisation) is ~10 weeks of work. Doable if you start *today* and ship a thinner version.
3. **Dynamic Video Workflows (#8)** — fits "Dynamic Software Interfaces" RFS. Could ship in 8 weeks. Horizontal-tool ICP risk.
4. **Watcher Agents (#3)** — broad agent thesis fit. Pick one ICP (hedge funds) and you have a clear pitch.

**Tier 3 — fundable but not YC-MVP-velocity:**

5. **AI-Native Compliance Service (#5)** — perfect RFS fit but compliance domain expertise + 12-week build means YC W27 (Sept window) is more realistic than S26.
6. **AI-Native Discovery Engine (#6)** — strong fit, but each vertical wants different things.
7. **AI-Native Video Editor (#2)** — biggest swing, hardest UX bar, slowest to demo-quality. YC pattern is right; timeline is wrong.

**Tier 4 — long-term plays, not the YC application:**

8. **F100 Video Intelligence (#9)** — needs an enterprise sales co-founder before YC.
9. **eDiscovery (#7)** — high ACV but YC-velocity-mismatched.
10. **Live Broadcast Agent Hub (#10)** — capital intensive, narrow buyer.

**Below Tier 4: Scrubless as a consumer video search app.** Beaten by an incumbent (Jumper), no agent angle, no RFS match.

---

## Part VI — The recommendation

**Apply to YC S26 with Pivot #1 (Stripe for Video), pitched as "the video understanding API every product with video buried inside it needs."** Consumer Scrubless stays live as the proof point ("we built the demo to prove the indexing works at scale; 12 dev teams have asked us to expose it as an API").

The 6-week plan is the one already sketched in conversation: API-key auth + project_id isolation + async ingest with webhooks → docs/curl examples → developer landing page → 3 design partners cold-emailed in week 5.

If you can also start a parallel track on **Company Brain (#4)** by getting one Zoom OAuth pilot working and indexing your own team's meetings, that's a powerful demo to *also* show in the YC interview. Two adjacent product directions running off the same engine is actually a strong founder narrative ("we built the engine; here are two ways customers are pulling it into different markets").

## Part VII — Things to NOT do

- Don't kill consumer Scrubless. Keep it free; let it grow as the demo.
- Don't pitch all 10 pivots in the YC application. Pick one; reference the engine.
- Don't take on the AI-Native Editor (#2) sized commitment with 6 weeks. It's the right idea for a $50M Series A pitch — but not the right idea to *promise YC by July 27*.
- Don't build the API multi-tenant story without adversarial security testing. One cross-tenant leak ends the company.
- Don't bother with NLE plugins or local-first as "competitive responses" — those are defensive plays in a niche that's not the bet.
