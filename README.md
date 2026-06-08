# Scrubless

> Stop scrubbing. Start searching.

Semantic video search — upload a video (or point at a folder of them), then find
the right moment in plain English. Live at **[getscrubless.com](https://getscrubless.com)**.

```
type "the part where someone is laughing"
        ↓
   ranked thumbnails with match scores
        ↓
   click → player jumps to the exact second
```

## What it does

- **Search inside a video** — visual *and* spoken, not just captions.
- **Library mode** — semantic search across an entire folder at once.
- **Ask** — questions about a video or a folder, answered in prose with
  clickable cited timestamps.
- **Auto-chapters & summaries** on every upload.
- **Highlight reels** — stitch search-result moments into one shareable clip.
- **Auth + billing** — Auth0 login, Stripe Checkout / Customer Portal, tiered
  upload caps.
- **Admin dashboard** — `/admin`, gated by `ADMIN_EMAILS`, with user / video /
  storage stats and a 7-day activity sparkline per event kind.

## Stack

Python (FastAPI), OpenCLIP ViT-B/32, ChromaDB, OpenAI Whisper, Anthropic Claude,
ffmpeg, SQLAlchemy (SQLite / Postgres), Auth0, Stripe, slowapi, Docker on
Railway. **One vanilla-JS `index.html` for the entire frontend — no build step.**

## Repo layout

```
clipfind/
├── app.py            # FastAPI entry — middleware, mounts, router wiring
├── config.py         # env vars, paths, tier caps
├── state.py          # in-memory VIDEOS / COLLECTIONS / REELS
├── ratelimit.py      # shared slowapi Limiter
├── models.py         # SQLAlchemy + persistence + record_event
├── embeddings.py     # CLIP model + Chroma collection + Claude helpers
├── auth.py           # Auth0 + current_user + is_admin + /api/auth/*
├── access.py         # ownership gates + gated /storage/{path}
├── billing.py        # Stripe + tier helpers + /api/billing/*
├── indexing.py       # ffmpeg + Whisper + process_video + sample/expiry
├── videos.py         # /api/upload + /api/status + /api/videos/{id}
├── library.py        # /api/library/* + /api/me/library
├── search.py         # /api/search/{id} + /api/qa/{id} + library variants
├── reels.py          # build_reel + /api/reel/*
├── admin.py          # /api/admin/stats + /admin
├── index.html        # entire frontend (vanilla JS, no build)
├── requirements.txt
├── Dockerfile, railway.toml
├── assets/sample.mp4 # auto-indexed demo (Big Buck Bunny)
├── scrubby/          # mascot SVGs + favicon
├── docs/             # ARCHITECTURE.md (source of truth) + pitch deck
└── storage/          # runtime: uploads, frames, chroma (gitignored)
```

## Run it

```bash
# 1. install deps + ffmpeg
pip install -r requirements.txt
brew install ffmpeg          # or: apt install ffmpeg

# 2. minimal .env (everything optional except SESSION_SECRET on HTTPS)
cat > .env <<'EOF'
SESSION_SECRET=change-me-to-a-strong-random-string
OPENAI_API_KEY=                 # transcription (else visual-only indexing)
ANTHROPIC_API_KEY=              # Vision enrichment, Q&A, chapters
ADMIN_EMAILS=you@example.com    # gates /admin
EOF

# 3. run
uvicorn app:app --reload --port 8080
open http://localhost:8080
```

Auth0 + Stripe vars are optional — without them, anonymous uploads still work
(capped at 500 MB, auto-deleted after 24 h).

## Read more

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — the source of truth.
  How indexing works, the data model, the security model, deployment, and the
  full change log.
- **[CLAUDE.md](CLAUDE.md)** — the V1 constraints the codebase is built under
  ("radical simplicity" — one backend file became 14 sibling modules but the
  same constraints still apply).
- **[docs/PITCH.pdf](docs/PITCH.pdf)** — the pitch deck.
