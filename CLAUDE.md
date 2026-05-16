# CLAUDE.md — Scrubless V1

## The Only Thing That Matters
Upload a video → search it with natural language → find the right moment.
That's V1. Nothing else ships until this works perfectly.

## Stack (ONE language, ZERO orchestration)
- **Everything:** Python (FastAPI)
- **Video processing:** ffmpeg (frames + audio, via subprocess)
- **Visual search:** OpenCLIP ViT-B/32 (loaded directly in the Python process, no sidecar)
- **Transcription:** OpenAI Whisper API (or yt-dlp captions for YouTube URLs)
- **Vector search:** ChromaDB (in-process, no Docker needed — `pip install chromadb`)
- **Search enrichment:** Anthropic Claude API (vision, top 3 results only)
- **Frontend:** Single HTML file with vanilla JS (no React, no Vite, no Tailwind, no build step)
- **Hosting:** Run locally. Demo via screen recording. Deploy to a single $5 VPS later if needed.

## NO:
- No Go
- No Docker / docker-compose
- No Terraform / AWS / ECS / S3 / CloudFront
- No React build pipeline
- No face recognition / InsightFace
- No knowledge graphs
- No YouTube video downloading (legal risk)
- No clip export (v2)
- No user accounts
- No sidecar services

## YouTube Support (LEGAL VERSION)
- User pastes a YouTube URL
- Backend calls yt-dlp ONLY for: metadata (title, duration, thumbnail) + auto-generated captions (.vtt)
- Backend does NOT download the video file
- Frontend embeds the YouTube iframe player for playback
- Captions are parsed and indexed alongside CLIP frame descriptions
- For CLIP indexing: extract frames from YouTube's thumbnail storyboard (legal) or ask user to also upload the file
- SIMPLEST PATH: V1 supports file upload only. YouTube URL is V1.1 after the demo works.

## Project Structure
```
scrubless/
├── app.py              # FastAPI server — ALL backend logic in one file
├── index.html          # Frontend — single file, served by FastAPI
├── requirements.txt    # pip install and go
├── .env                # API keys
└── storage/            # Uploaded videos, extracted frames
```

## app.py — What It Does

### Startup
- Load OpenCLIP model (ViT-B/32) into memory
- Initialize ChromaDB (persistent, local directory)
- Mount static file serving for /storage

### POST /api/upload
- Accept video file (multipart)
- Save to storage/{video_id}/source.mp4
- Return {id, status: "processing"}
- Kick off background processing (asyncio / BackgroundTasks):
  1. ffmpeg: extract frames every 5 seconds → storage/{video_id}/frames/
  2. ffmpeg: extract audio → storage/{video_id}/audio.wav
  3. Whisper API: transcribe audio → word-level timestamps → segment into 15-30s chunks
  4. For each frame: load image → CLIP encode → get embedding vector
  5. Store in ChromaDB: embedding + metadata {video_id, timestamp, frame_path, transcript_segment}
  6. Update status to "indexed"

### GET /api/status/{video_id}
- Return {status: "processing" | "indexed" | "error", progress: int, total_segments: int}

### POST /api/search/{video_id}
- Accept {query: string}
- CLIP encode the query text → embedding vector
- ChromaDB query: cosine similarity → top 10 results
- For top 3 results: call Claude Vision API with the frame image
  - Prompt: "Describe what's happening in this frame in 1-2 sentences."
- Return [{timestamp, frame_url, score, description, transcript_snippet}]

### GET /
- Serve index.html

## index.html — What It Does

Single HTML file. No build step. Vanilla JS + minimal CSS.

1. **Upload section:** drag-and-drop or file picker. POST to /api/upload.
2. **Processing section:** poll /api/status every 2 seconds. Show progress bar.
3. **Search section:** text input + search button. POST to /api/search.
4. **Results section:** grid of results. Each result shows: thumbnail, timestamp, score, description, transcript snippet.
5. **Player section:** HTML5 <video> element. Click a result → video.currentTime = timestamp.

That's the whole frontend. No components, no hooks, no state management. Just DOM manipulation.

## requirements.txt
```
fastapi>=0.104.0
uvicorn>=0.24.0
python-multipart>=0.0.6
open-clip-torch>=2.24.0
torch>=2.1.0
Pillow>=10.0.0
chromadb>=0.4.0
anthropic>=0.39.0
openai>=1.0.0
python-dotenv>=1.0.0
```

## .env
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Commands
```bash
# Setup
pip install -r requirements.txt
# Make sure ffmpeg is installed: brew install ffmpeg (mac) or apt install ffmpeg (linux)

# Run
uvicorn app:app --reload --port 8080

# Open
open http://localhost:8080
```

## Build Order (TONIGHT)
1. Create requirements.txt → pip install
2. Write app.py: FastAPI skeleton + file upload endpoint + static serving
3. Add ffmpeg frame extraction (subprocess)
4. Add CLIP model loading + frame embedding
5. Add ChromaDB storage
6. Add Whisper transcription
7. Add search endpoint (CLIP text embed → ChromaDB query)
8. Add Claude Vision enrichment of top 3 results
9. Write index.html: upload → progress → search → results → player
10. TEST WITH A REAL VIDEO. Run 20 queries. Does it find the right moments?
11. Screen-record the demo for YC video.

## What "Done" Looks Like Tonight
You upload a 30-minute video of you and your friends. You type "find the part where someone is laughing." The right moment comes back with a thumbnail. You click it. The video plays from that exact timestamp.

If that doesn't work, nothing else matters.

## After Tonight (V1.1, V1.2...)
- YouTube URL support (metadata + captions only, legal)
- Cloud deployment (single VPS, not AWS ECS)
- Clip export
- Better frontend (React rewrite)
- Face recognition (after legal review)
- Mobile support
