"""Background indexing pipeline (ffmpeg + Whisper + CLIP + Claude chapters),
plus the boot-time helpers: sample ingestion, expiry sweep, state restore."""
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import FRAME_INTERVAL, OPENAI_API_KEY, ROOT, STORAGE, VIDEO_TTL_SECONDS
from embeddings import embed_image, segments, summarize_video
from models import Collection, Video, engine, forget_video, persist_video
from state import COLLECTIONS, SAMPLE_ID, VIDEOS


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


def transcript_context(video_id, limit=14000):
    """Rebuild a timestamped transcript for a video from its ChromaDB segments."""
    try:
        got = segments.get(where={"video_id": video_id})
    except Exception:  # noqa: BLE001
        return ""
    metas = got.get("metadatas") or []
    rows = sorted(metas, key=lambda m: m.get("timestamp", 0))
    lines, prev = [], None
    for m in rows:
        txt = (m.get("transcript_segment") or "").strip()
        if not txt or txt == prev:  # skip blanks + overlapping repeats
            continue
        lines.append("[%ds] %s" % (int(m.get("timestamp", 0)), txt))
        prev = txt
    return "\n".join(lines)[:limit]


# --------------------------------------------------------------------------
# Indexing pipeline (runs in a background thread)
# --------------------------------------------------------------------------
def process_video(video_id):
    """Extract frames + audio, transcribe, CLIP-embed, store in ChromaDB."""
    video = VIDEOS[video_id]
    try:
        vdir = STORAGE / video_id
        source = Path(video["source"])

        # Clear any stale segments so re-indexing (e.g. resuming after a
        # restart) is idempotent instead of producing duplicates.
        try:
            segments.delete(where={"video_id": video_id})
        except Exception:  # noqa: BLE001
            pass

        frames = extract_frames(source, vdir / "frames")
        if not frames:
            raise RuntimeError("no frames extracted from video")

        transcript = []
        try:
            audio_path = vdir / "audio.mp3"
            extract_audio(source, audio_path)
            transcript = transcribe(audio_path)
        except Exception as exc:  # noqa: BLE001
            print("[scrubless] %s: skipping transcript (%s)" % (video_id, exc))

        cid = video.get("collection_id") or ""  # "" for standalone uploads
        ids, embs, metadatas, documents = [], [], [], []
        for i, frame in enumerate(frames):
            start = i * FRAME_INTERVAL
            end = start + FRAME_INTERVAL
            snippet = transcript_for_window(transcript, start, end)

            ids.append("%s-%d" % (video_id, i))
            embs.append(embed_image(frame))
            metadatas.append(
                {
                    "video_id": video_id,
                    "collection_id": cid,
                    "timestamp": start,
                    "frame_path": "/storage/%s/frames/%s" % (video_id, frame.name),
                    "transcript_segment": snippet,
                }
            )
            documents.append(snippet)
            video["progress"] = int((i + 1) / len(frames) * 100)

        segments.add(
            ids=ids,
            embeddings=embs,
            metadatas=metadatas,
            documents=documents,
        )
        video["total_segments"] = len(frames)
        video["status"] = "indexed"
        print("[scrubless] %s indexed (%d segments)" % (video_id, len(frames)))

        try:
            meta = summarize_video(transcript)
            if meta:
                video["summary"] = meta.get("summary", "")
                video["chapters"] = meta.get("chapters", [])
                print("[scrubless] %s: %d chapters" % (video_id, len(video["chapters"])))
        except Exception as exc:  # noqa: BLE001
            print("[scrubless] %s: chapters skipped (%s)" % (video_id, exc))
    except Exception as exc:  # noqa: BLE001
        video["status"] = "error"
        video["error"] = str(exc)
        print("[scrubless] %s failed: %s" % (video_id, exc))
    persist_video(video_id)  # save the final status (no-op for the sample)


# --------------------------------------------------------------------------
# Sample video — auto-indexed at startup so a visitor can try search without
# uploading anything. Storage is ephemeral (e.g. on Railway), so this re-runs
# on every boot; it's cheap for a short clip.
# --------------------------------------------------------------------------
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
# Deletion + auto-expiry (free tier: no account, videos don't linger)
# --------------------------------------------------------------------------
def delete_video(video_id):
    """Remove a video's record, stored files, and index entries."""
    v = VIDEOS.pop(video_id, None)
    if v and v.get("collection_id"):  # drop it from its collection too
        coll = COLLECTIONS.get(v["collection_id"])
        if coll and video_id in coll["video_ids"]:
            coll["video_ids"].remove(video_id)
    forget_video(video_id)
    try:
        segments.delete(where={"video_id": video_id})
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] delete index %s: %s" % (video_id, exc))
    shutil.rmtree(STORAGE / video_id, ignore_errors=True)


def expiry_sweep():
    """Periodically delete uploads older than the TTL (never the sample)."""
    while True:
        time.sleep(1800)
        now = time.time()
        for vid, v in list(VIDEOS.items()):
            if vid == SAMPLE_ID or v.get("owner"):  # keep sample + account videos
                continue
            if now - v.get("created", now) > VIDEO_TTL_SECONDS:
                print("[scrubless] auto-expiring %s" % vid)
                delete_video(vid)


def restore_state():
    """Rebuild VIDEOS/COLLECTIONS from the DB after a restart, and resume any
    indexing that didn't finish. Needs the storage volume to be persistent for
    the referenced files + embeddings to still exist."""
    try:
        with Session(engine) as s:
            for c in s.scalars(select(Collection)).all():
                COLLECTIONS[c.id] = {
                    "name": c.name,
                    "path": c.path,
                    "video_ids": [],
                    "created": c.created,
                    "owner": c.owner,
                }
            for v in s.scalars(select(Video)).all():
                try:
                    chapters = json.loads(v.chapters or "[]")
                except Exception:  # noqa: BLE001
                    chapters = []
                VIDEOS[v.id] = {
                    "status": v.status,
                    "progress": 100 if v.status == "indexed" else 0,
                    "total_segments": v.total_segments,
                    "error": "",
                    "source": v.source,
                    "title": v.title,
                    "created": v.created,
                    "owner": v.owner,
                    "collection_id": v.collection_id or None,
                    "summary": v.summary or "",
                    "chapters": chapters,
                }
                if v.collection_id and v.collection_id in COLLECTIONS:
                    COLLECTIONS[v.collection_id]["video_ids"].append(v.id)
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] restore_state failed: %s" % exc)
        return

    if VIDEOS:
        print(
            "[scrubless] restored %d videos, %d collections"
            % (len(VIDEOS), len(COLLECTIONS))
        )
    # Resume anything that didn't finish indexing before the restart.
    for vid, v in list(VIDEOS.items()):
        if v["status"] != "indexed":
            if Path(v["source"]).exists():
                print("[scrubless] resuming index for %s" % vid)
                threading.Thread(target=process_video, args=(vid,), daemon=True).start()
            else:
                v["status"] = "error"
                v["error"] = "source missing after restart"
                persist_video(vid)
