# Scrubless

**Stop scrubbing. Start searching.**

Semantic video search. Upload a video, then find any moment by describing it
in plain language — "the part where someone starts laughing" jumps you right
there.

## How it works

1. **ffmpeg** extracts a frame every 5 seconds, plus the audio track.
2. **OpenCLIP** (`ViT-B/32`) embeds each frame into a vector.
3. **Whisper** transcribes the audio (optional — needs an OpenAI key).
4. **ChromaDB** stores the vectors. A text query is CLIP-embedded and matched
   by cosine similarity.
5. **Claude Vision** describes the top results (optional — needs an Anthropic key).

## Stack

Single-file Python backend (FastAPI) + single-file vanilla-JS frontend.
No build step, no Docker, no orchestration. CLIP and ChromaDB run in-process.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# ffmpeg is required:  brew install ffmpeg  (macOS)  /  apt install ffmpeg  (Linux)

cp .env.example .env          # optional: add OpenAI + Anthropic API keys
.venv/bin/uvicorn app:app --port 8080
```

Open <http://localhost:8080>. Without API keys it still works — transcription
and result descriptions are simply skipped.

## Project layout

```
app.py            # the entire backend
index.html        # the entire frontend
requirements.txt  # Python dependencies
legacy/           # earlier Go + React + Docker architecture, archived
```
