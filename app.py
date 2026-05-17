"""Scrubless V1 — semantic video search, all in one file.

Upload a video, it gets indexed (ffmpeg frames + Whisper transcript + CLIP
embeddings in ChromaDB), then you search it with natural language.

Run:  uvicorn app:app --port 8080
"""

import base64
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

import chromadb
import open_clip
import torch
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

load_dotenv()

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
ROOT = Path(__file__).parent
STORAGE = ROOT / "storage"
STORAGE.mkdir(exist_ok=True)

FRAME_INTERVAL = 5  # seconds between extracted frames
ENRICH_TOP_N = 3  # how many top results get a Claude Vision description

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# --------------------------------------------------------------------------
# Models / clients — loaded once at startup
# --------------------------------------------------------------------------
print("[scrubless] loading OpenCLIP ViT-B-32 …")
clip_model, _, clip_preprocess = open_clip.create_model_and_transforms(
    "ViT-B-32", pretrained="laion2b_s34b_b79k"
)
clip_tokenizer = open_clip.get_tokenizer("ViT-B-32")
clip_model.eval()
print("[scrubless] CLIP ready")

chroma = chromadb.PersistentClient(path=str(STORAGE / "chroma"))
segments = chroma.get_or_create_collection(
    "segments", metadata={"hnsw:space": "cosine"}
)

# In-memory video state. Lost on restart — fine for V1 (run locally, demo).
VIDEOS = {}  # video_id -> {status, progress, total_segments, error, source, title}

app = FastAPI(title="Scrubless")
app.mount("/storage", StaticFiles(directory=str(STORAGE)), name="storage")
app.mount("/scrubby", StaticFiles(directory=str(ROOT / "scrubby")), name="scrubby")


# --------------------------------------------------------------------------
# CLIP embedding
# --------------------------------------------------------------------------
def embed_image(path):
    """Return the CLIP embedding of an image file as a list of floats."""
    image = clip_preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        vec = clip_model.encode_image(image)
        vec /= vec.norm(dim=-1, keepdim=True)
    return vec[0].tolist()


def embed_text(text):
    """Return the CLIP embedding of a text query as a list of floats."""
    tokens = clip_tokenizer([text])
    with torch.no_grad():
        vec = clip_model.encode_text(tokens)
        vec /= vec.norm(dim=-1, keepdim=True)
    return vec[0].tolist()


# --------------------------------------------------------------------------
# ffmpeg helpers
# --------------------------------------------------------------------------
def extract_frames(source, frames_dir):
    """Extract one JPEG every FRAME_INTERVAL seconds; return sorted paths."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source),
            "-vf", "fps=1/%d" % FRAME_INTERVAL,
            "-q:v", "2",
            str(frames_dir / "frame_%04d.jpg"),
        ],
        check=True,
    )
    return sorted(frames_dir.glob("frame_*.jpg"))


def extract_audio(source, audio_path):
    """Extract a 16kHz mono MP3 — small enough to send to the Whisper API."""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source),
            "-vn", "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1",
            "-b:a", "48k",
            str(audio_path),
        ],
        check=True,
    )


# --------------------------------------------------------------------------
# Transcription (Whisper) — optional, skipped without an API key
# --------------------------------------------------------------------------
def transcribe(audio_path):
    """Transcribe audio into [{start, end, text}] segments via Whisper."""
    if not OPENAI_API_KEY:
        print("[scrubless] no OPENAI_API_KEY — indexing visual-only")
        return []
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model="whisper-1", file=f, response_format="verbose_json"
        )

    out = []
    for seg in getattr(resp, "segments", None) or []:
        # segments may be typed objects or plain dicts depending on SDK build
        get = (lambda k: seg.get(k)) if isinstance(seg, dict) else (lambda k: getattr(seg, k))
        out.append({"start": get("start"), "end": get("end"), "text": get("text") or ""})
    return out


def transcript_for_window(transcript, start, end):
    """Join transcript text overlapping the half-open window [start, end)."""
    parts = [
        t["text"].strip()
        for t in transcript
        if t["start"] < end and t["end"] > start and t["text"].strip()
    ]
    return " ".join(parts)


# --------------------------------------------------------------------------
# Search-time enrichment (Claude Vision) — optional
# --------------------------------------------------------------------------
def describe_frame(frame_path):
    """Return a 1-2 sentence Claude Vision description of a frame, or ''."""
    if not ANTHROPIC_API_KEY:
        return ""
    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    with open(frame_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Describe what's happening in this frame in 1-2 sentences.",
                        },
                    ],
                }
            ],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception as exc:  # noqa: BLE001 — enrichment is best-effort
        print("[scrubless] enrich failed:", exc)
        return ""


# --------------------------------------------------------------------------
# Indexing pipeline (runs in a background thread)
# --------------------------------------------------------------------------
def process_video(video_id):
    """Extract frames + audio, transcribe, CLIP-embed, store in ChromaDB."""
    video = VIDEOS[video_id]
    try:
        vdir = STORAGE / video_id
        source = Path(video["source"])

        frames = extract_frames(source, vdir / "frames")
        if not frames:
            raise RuntimeError("no frames extracted from video")

        # Audio is optional — a video may have no audio track at all. If
        # extraction or transcription fails, index visually and move on.
        transcript = []
        try:
            audio_path = vdir / "audio.mp3"
            extract_audio(source, audio_path)
            transcript = transcribe(audio_path)
        except Exception as exc:  # noqa: BLE001
            print("[scrubless] %s: skipping transcript (%s)" % (video_id, exc))

        ids, embeddings, metadatas, documents = [], [], [], []
        for i, frame in enumerate(frames):
            start = i * FRAME_INTERVAL
            end = start + FRAME_INTERVAL
            snippet = transcript_for_window(transcript, start, end)

            ids.append("%s-%d" % (video_id, i))
            embeddings.append(embed_image(frame))
            metadatas.append(
                {
                    "video_id": video_id,
                    "timestamp": start,
                    "frame_path": "/storage/%s/frames/%s" % (video_id, frame.name),
                    "transcript_segment": snippet,
                }
            )
            documents.append(snippet)
            video["progress"] = int((i + 1) / len(frames) * 100)

        segments.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        video["total_segments"] = len(frames)
        video["status"] = "indexed"
        print("[scrubless] %s indexed (%d segments)" % (video_id, len(frames)))
    except Exception as exc:  # noqa: BLE001
        video["status"] = "error"
        video["error"] = str(exc)
        print("[scrubless] %s failed: %s" % (video_id, exc))


# --------------------------------------------------------------------------
# Sample video — auto-indexed at startup so a visitor can try search without
# uploading anything. Storage is ephemeral (e.g. on Railway), so this re-runs
# on every boot; it's cheap for a short clip.
# --------------------------------------------------------------------------
SAMPLE_ID = "sample"


def ingest_sample():
    """Copy and index the bundled sample video under the id 'sample'."""
    src = ROOT / "assets" / "sample.mp4"
    if not src.exists():
        print("[scrubless] no assets/sample.mp4 — skipping sample video")
        return

    vdir = STORAGE / SAMPLE_ID
    vdir.mkdir(parents=True, exist_ok=True)
    dst = vdir / "source.mp4"
    shutil.copy(src, dst)

    # Drop any stale index for the sample (ChromaDB persists across restarts).
    try:
        segments.delete(where={"video_id": SAMPLE_ID})
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] sample: clear old index:", exc)

    VIDEOS[SAMPLE_ID] = {
        "status": "processing",
        "progress": 0,
        "total_segments": 0,
        "error": "",
        "source": str(dst),
        "title": "Sample video — Big Buck Bunny",
    }
    print("[scrubless] indexing sample video…")
    process_video(SAMPLE_ID)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str


@app.post("/api/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    video_id = uuid.uuid4().hex[:12]
    vdir = STORAGE / video_id
    vdir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "").suffix.lower() or ".mp4"
    source = vdir / ("source" + ext)
    with open(source, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)

    VIDEOS[video_id] = {
        "status": "processing",
        "progress": 0,
        "total_segments": 0,
        "error": "",
        "source": str(source),
        "title": file.filename or "Untitled",
    }
    background_tasks.add_task(process_video, video_id)
    return {"id": video_id, "status": "processing"}


@app.get("/api/status/{video_id}")
def status(video_id: str):
    video = VIDEOS.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")
    return {
        "status": video["status"],
        "progress": video["progress"],
        "total_segments": video["total_segments"],
        "error": video["error"],
        "title": video["title"],
        "source_url": "/storage/%s/%s" % (video_id, Path(video["source"]).name),
    }


@app.post("/api/search/{video_id}")
def search(video_id: str, req: SearchRequest):
    video = VIDEOS.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")
    if video["status"] != "indexed":
        raise HTTPException(status_code=409, detail="video is not indexed yet")

    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    result = segments.query(
        query_embeddings=[embed_text(query)],
        n_results=10,
        where={"video_id": video_id},
    )
    metas = result["metadatas"][0]
    dists = result["distances"][0]

    results = []
    for meta, dist in zip(metas, dists):
        results.append(
            {
                "timestamp": meta["timestamp"],
                "frame_url": meta["frame_path"],
                "score": round(1.0 - dist, 4),  # cosine similarity
                "description": "",
                "transcript_snippet": meta.get("transcript_segment", ""),
            }
        )

    # Enrich the top results with Claude Vision descriptions.
    for item in results[:ENRICH_TOP_N]:
        local_path = ROOT / item["frame_url"].lstrip("/")
        item["description"] = describe_frame(local_path)

    return results


@app.get("/")
def index():
    return FileResponse(str(ROOT / "index.html"))


# Index the bundled sample video in the background as the server starts.
threading.Thread(target=ingest_sample, daemon=True).start()
