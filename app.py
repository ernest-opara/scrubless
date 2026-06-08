"""Scrubless V1 — semantic video search, all in one file.

Upload a video, it gets indexed (ffmpeg frames + Whisper transcript + CLIP
embeddings in ChromaDB), then you search it with natural language.

Run:  uvicorn app:app --port 8080
"""

import base64
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

import chromadb
import open_clip
import stripe
import torch
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import Float, String, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from starlette.middleware.sessions import SessionMiddleware

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

# Comma-separated emails (case-insensitive) allowed into /admin.
ADMIN_EMAILS = {
    e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
}

# Auth (Auth0) + sessions + database
SESSION_SECRET = (
    os.getenv("SESSION_SECRET")
    or os.getenv("AUTH0_SECRET")  # the name Auth0's quickstart generates
    or "dev-insecure-change-me"
)
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8080").rstrip("/")
AUTH0_DOMAIN = (
    os.getenv("AUTH0_DOMAIN", "")
    .strip()
    .removeprefix("https://")
    .removeprefix("http://")
    .rstrip("/")
)  # tolerate a pasted scheme/trailing slash
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "").strip()
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + str(ROOT / "scrubless.db"))
if DATABASE_URL.startswith("postgres://"):  # Railway sometimes uses the old scheme
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Per-tier upload caps (bytes). Anonymous == free; paid tiers raise the cap.
MB = 1024 * 1024
GB = 1024 * MB
ANON_LIMIT = 500 * MB
TIER_LIMITS = {"free": 500 * MB, "pro": 2 * GB, "studio": 10 * GB}

# Stripe billing
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "").strip()
STRIPE_PRICE_STUDIO = os.getenv("STRIPE_PRICE_STUDIO", "").strip()
TIER_TO_PRICE = {"pro": STRIPE_PRICE_PRO, "studio": STRIPE_PRICE_STUDIO}
PRICE_TO_TIER = {price: tier for tier, price in TIER_TO_PRICE.items() if price}

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

# Library Mode (V2): a collection groups many videos (e.g. a scanned folder),
# so one query can search across all of them.
COLLECTIONS = {}  # collection_id -> {name, path, video_ids, created}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv"}

app = FastAPI(title="Scrubless")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
# Static-mount only the public mascot. Storage is gated by storage_serve() below
# so an uploader's videos / frames are only visible to the uploader (logged-in
# users by owner; anonymous uploads by per-session allowlist).
app.mount("/scrubby", StaticFiles(directory=str(ROOT / "scrubby")), name="scrubby")


# --------------------------------------------------------------------------
# Accounts (SQLite in dev, Postgres in prod) + Auth0 login
# --------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    auth0_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    tier: Mapped[str] = mapped_column(String(20), default="free")
    stripe_customer_id: Mapped[str] = mapped_column(String(255), default="")
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Video(Base):
    """Durable metadata for an indexed video — lets VIDEOS rebuild on restart.
    The frames + embeddings themselves live on the storage volume."""

    __tablename__ = "videos"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    collection_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    source: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(20), default="processing")
    total_segments: Mapped[int] = mapped_column(default=0)
    owner: Mapped[Optional[int]] = mapped_column(nullable=True, default=None)
    created: Mapped[float] = mapped_column(Float, default=time.time)
    summary: Mapped[str] = mapped_column(String(2000), default="")
    chapters: Mapped[str] = mapped_column(String(4000), default="")  # JSON list


class Collection(Base):
    """Durable metadata for a scanned/uploaded folder."""

    __tablename__ = "collections"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(512), default="")
    path: Mapped[str] = mapped_column(String(1024), default="")
    created: Mapped[float] = mapped_column(Float, default=time.time)
    owner: Mapped[Optional[int]] = mapped_column(nullable=True, default=None)


class Event(Base):
    """Lightweight activity log for the admin dashboard — every visit, search,
    Q&A, upload, and reel writes one row. Aggregated by kind + time window."""

    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    at: Mapped[float] = mapped_column(Float, default=time.time, index=True)


_engine_args = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_args["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **_engine_args)
Base.metadata.create_all(engine)


def ensure_columns():
    """Add columns introduced after a table was first created (create_all won't
    alter an existing table). Cross-DB, idempotent, best-effort. The spec is
    the full SQL after `ADD COLUMN <name>` so each column carries its own
    DEFAULT (text vs integer can't share one)."""
    wanted = {
        "videos": {
            "summary": "VARCHAR(2000) DEFAULT ''",
            "chapters": "VARCHAR(4000) DEFAULT ''",
        },
        "collections": {"owner": "INTEGER DEFAULT NULL"},
    }
    insp = inspect(engine)
    for table, cols in wanted.items():
        try:
            existing = {c["name"] for c in insp.get_columns(table)}
        except Exception:
            continue  # table doesn't exist yet — create_all already made it
        for name, spec in cols.items():
            if name in existing:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, spec)))
                print("[scrubless] migrated: added %s.%s" % (table, name))
            except Exception as exc:  # noqa: BLE001
                print("[scrubless] add column %s.%s: %s" % (table, name, exc))


ensure_columns()

oauth = OAuth()
AUTH0_ENABLED = bool(AUTH0_DOMAIN and AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET)
if AUTH0_ENABLED:
    oauth.register(
        "auth0",
        client_id=AUTH0_CLIENT_ID,
        client_secret=AUTH0_CLIENT_SECRET,
        client_kwargs={"scope": "openid profile email"},
        server_metadata_url="https://%s/.well-known/openid-configuration" % AUTH0_DOMAIN,
    )
    print("[scrubless] Auth0 login enabled")
else:
    print("[scrubless] Auth0 not configured — anonymous uploads only (<=500MB)")

STRIPE_ENABLED = bool(STRIPE_SECRET_KEY)
if STRIPE_ENABLED:
    stripe.api_key = STRIPE_SECRET_KEY
    print("[scrubless] Stripe billing enabled")
else:
    print("[scrubless] Stripe not configured — all accounts stay free")


def current_user(request):
    """Return the logged-in User, or None."""
    uid = request.session.get("user_id")
    if not uid:
        return None
    with Session(engine) as s:
        return s.get(User, uid)


def is_admin(user):
    return bool(user and user.email and user.email.lower() in ADMIN_EMAILS)


def record_event(kind):
    """Fire-and-forget activity log; never block a request on a tracking write."""
    try:
        with Session(engine) as s:
            s.add(Event(kind=kind, at=time.time()))
            s.commit()
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] record_event %s failed: %s" % (kind, exc))


# --------------------------------------------------------------------------
# Access control
# --------------------------------------------------------------------------
SAMPLE_ID = "sample"


def remember_anon_resource(request: Request, kind: str, rid: str):
    """Remember that this anonymous session owns this video/collection/reel.
    Lets the SAME browser session keep accessing what it just uploaded without
    a login, while a different visitor can't reach it by guessing the id."""
    key = "my_" + kind
    owned = request.session.get(key) or []
    if rid not in owned:
        owned.append(rid)
        # cap so an attacker can't bloat the cookie
        request.session[key] = owned[-200:]


def _owned_by_session(request: Request, kind: str, rid: str) -> bool:
    return rid in (request.session.get("my_" + kind) or [])


def can_access_video(video_id: str, request: Request) -> bool:
    if video_id == SAMPLE_ID:
        return True
    video = VIDEOS.get(video_id)
    if not video:
        return False
    user = current_user(request)
    if is_admin(user):
        return True
    owner = video.get("owner")
    if owner is not None:
        return bool(user and user.id == owner)
    return _owned_by_session(request, "videos", video_id)


def can_access_collection(collection_id: str, request: Request) -> bool:
    coll = COLLECTIONS.get(collection_id)
    if not coll:
        return False
    user = current_user(request)
    if is_admin(user):
        return True
    owner = coll.get("owner")
    if owner is not None:
        return bool(user and user.id == owner)
    return _owned_by_session(request, "collections", collection_id)


def can_access_reel(reel_id: str, request: Request) -> bool:
    reel = REELS.get(reel_id)
    if not reel:
        return False
    user = current_user(request)
    if is_admin(user):
        return True
    owner = reel.get("owner")
    if owner is not None:
        return bool(user and user.id == owner)
    return _owned_by_session(request, "reels", reel_id)


def require_video(video_id: str, request: Request) -> dict:
    """Return the video dict if the caller may access it, else raise 404.
    Using 404 (not 403) prevents enumeration of valid video ids."""
    if not can_access_video(video_id, request):
        raise HTTPException(status_code=404, detail="video not found")
    return VIDEOS[video_id]


def require_collection(collection_id: str, request: Request) -> dict:
    if not can_access_collection(collection_id, request):
        raise HTTPException(status_code=404, detail="collection not found")
    return COLLECTIONS[collection_id]


def safe_video_ext(filename: str) -> str:
    """Return a safe video extension from a user-supplied filename, or .mp4.
    Refusing non-video extensions prevents serving an attacker's .html/.svg
    from our own origin via the storage route (stored-XSS)."""
    ext = Path(filename or "").suffix.lower()
    return ext if ext in VIDEO_EXTS else ".mp4"


@app.get("/storage/{rest:path}")
def storage_serve(rest: str, request: Request):
    """Gated replacement for the previous public StaticFiles mount.
    Resolves the path under STORAGE (rejecting traversal), then checks access
    based on whether the first path segment is a video_id or a reel id."""
    target = (STORAGE / rest).resolve()
    storage_root = STORAGE.resolve()
    if storage_root != target and storage_root not in target.parents:
        raise HTTPException(status_code=404, detail="not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    first = rest.split("/", 1)[0]
    if first == "reels":
        reel_id = Path(rest).stem
        if not can_access_reel(reel_id, request):
            raise HTTPException(status_code=404, detail="not found")
    else:
        if not can_access_video(first, request):
            raise HTTPException(status_code=404, detail="not found")
    return FileResponse(str(target))


def upload_limit_for(user):
    return TIER_LIMITS.get(user.tier, ANON_LIMIT) if user else ANON_LIMIT


def over_cap_detail(user, cap):
    mb = cap // MB
    if user is None:
        return "Files over %dMB need an account — sign in to upload larger videos." % mb
    return "Your %s plan allows up to %dMB — upgrade for larger uploads." % (user.tier, mb)


def stripe_customer_for(user):
    """Return the user's Stripe customer id, creating one if needed."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    cust = stripe.Customer.create(
        email=user.email or None, metadata={"user_id": str(user.id)}
    )
    with Session(engine) as s:
        u = s.get(User, user.id)
        u.stripe_customer_id = cust.id
        s.commit()
    return cust.id


def set_tier_by_customer(customer_id, tier, sub_id=""):
    """Update a user's tier from a Stripe webhook, keyed by customer id."""
    if not customer_id:
        return
    with Session(engine) as s:
        u = s.scalar(select(User).where(User.stripe_customer_id == customer_id))
        if u:
            u.tier = tier
            u.stripe_subscription_id = sub_id or ""
            s.commit()
            print("[scrubless] billing: %s -> %s" % (u.email, tier))


# --------------------------------------------------------------------------
# Durable state — mirror the VIDEOS/COLLECTIONS dicts into the DB so a restart
# (e.g. a Railway redeploy) doesn't lose the library. Files + embeddings live on
# the storage volume; these tables hold the metadata needed to rebuild the dicts.
# --------------------------------------------------------------------------
def persist_video(video_id):
    if video_id == SAMPLE_ID:
        return  # the sample is re-indexed on every boot
    v = VIDEOS.get(video_id)
    if not v:
        return
    try:
        with Session(engine) as s:
            s.merge(
                Video(
                    id=video_id,
                    collection_id=v.get("collection_id") or "",
                    title=v.get("title") or "",
                    source=v.get("source") or "",
                    status=v.get("status") or "processing",
                    total_segments=v.get("total_segments") or 0,
                    owner=v.get("owner"),
                    created=v.get("created") or time.time(),
                    summary=v.get("summary") or "",
                    chapters=json.dumps(v.get("chapters") or []),
                )
            )
            s.commit()
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] persist_video %s: %s" % (video_id, exc))


def persist_collection(collection_id):
    c = COLLECTIONS.get(collection_id)
    if not c:
        return
    try:
        with Session(engine) as s:
            s.merge(
                Collection(
                    id=collection_id,
                    name=c.get("name") or "",
                    path=c.get("path") or "",
                    created=c.get("created") or time.time(),
                    owner=c.get("owner"),
                )
            )
            s.commit()
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] persist_collection %s: %s" % (collection_id, exc))


def forget_video(video_id):
    try:
        with Session(engine) as s:
            row = s.get(Video, video_id)
            if row:
                s.delete(row)
                s.commit()
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] forget_video %s: %s" % (video_id, exc))


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


def summarize_video(transcript):
    """Return {"summary", "chapters"} from a transcript via Claude, or {}.

    Best-effort: needs an Anthropic key and a transcript (so visual-only videos
    just get no chapters).
    """
    if not ANTHROPIC_API_KEY or not transcript:
        return {}
    lines = []
    for t in transcript:
        txt = (t.get("text") or "").strip()
        if txt:
            lines.append("[%ds] %s" % (int(t["start"]), txt))
    if not lines:
        return {}
    body = "\n".join(lines)[:12000]  # cap input tokens
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = (
            "Below is a timestamped transcript of a video.\n\n"
            + body
            + '\n\nReturn ONLY a JSON object: {"summary": "<2-3 sentence overview>", '
            '"chapters": [{"start": <seconds int>, "title": "<short title>"}]} '
            "with 4-8 chapters in chronological order. No markdown, just JSON."
        )
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        out = "".join(b.text for b in msg.content if b.type == "text")
        i, j = out.find("{"), out.rfind("}")
        if i < 0 or j <= i:
            return {}
        data = json.loads(out[i : j + 1])
        chapters = []
        for c in data.get("chapters", []):
            try:
                chapters.append({"start": int(c["start"]), "title": str(c["title"])[:120]})
            except Exception:  # noqa: BLE001 — skip a malformed chapter
                continue
        return {"summary": str(data.get("summary", ""))[:1500], "chapters": chapters}
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] summarize failed:", exc)
        return {}


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

        # Audio is optional — a video may have no audio track at all. If
        # extraction or transcription fails, index visually and move on.
        transcript = []
        try:
            audio_path = vdir / "audio.mp3"
            extract_audio(source, audio_path)
            transcript = transcribe(audio_path)
        except Exception as exc:  # noqa: BLE001
            print("[scrubless] %s: skipping transcript (%s)" % (video_id, exc))

        cid = video.get("collection_id") or ""  # "" for standalone uploads
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
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        video["total_segments"] = len(frames)
        video["status"] = "indexed"
        print("[scrubless] %s indexed (%d segments)" % (video_id, len(frames)))

        # Auto-chapters + summary (best-effort; needs transcript + Claude key).
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
# SAMPLE_ID is declared earlier (next to the access-control helpers).


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
# Deletion + auto-expiry (free tier: no account, videos don't linger)
# --------------------------------------------------------------------------
VIDEO_TTL_SECONDS = 24 * 3600  # free uploads auto-expire after 24h


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


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str


@app.get("/api/auth/login")
async def auth_login(request: Request):
    if not AUTH0_ENABLED:
        raise HTTPException(status_code=503, detail="login is not configured")
    return await oauth.auth0.authorize_redirect(request, APP_BASE_URL + "/api/auth/callback")


@app.get("/api/auth/callback")
async def auth_callback(request: Request):
    if not AUTH0_ENABLED:
        raise HTTPException(status_code=503, detail="login is not configured")
    token = await oauth.auth0.authorize_access_token(request)
    info = token.get("userinfo") or {}
    sub = info.get("sub")
    email = (info.get("email") or "").lower()
    if not sub:
        raise HTTPException(status_code=400, detail="no identity returned")
    with Session(engine) as s:
        user = s.scalar(select(User).where(User.auth0_sub == sub))
        if user is None:
            user = User(auth0_sub=sub, email=email, tier="free", created_at=time.time())
            s.add(user)
            s.commit()
            s.refresh(user)
        elif email and user.email != email:
            user.email = email
            s.commit()
        request.session["user_id"] = user.id
    return RedirectResponse("/")


@app.get("/api/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    if AUTH0_ENABLED:
        return RedirectResponse(
            "https://%s/v2/logout?client_id=%s&returnTo=%s"
            % (AUTH0_DOMAIN, AUTH0_CLIENT_ID, APP_BASE_URL + "/")
        )
    return RedirectResponse("/")


@app.get("/api/auth/me")
def auth_me(request: Request):
    user = current_user(request)
    return {
        "user": (
            {"email": user.email, "tier": user.tier, "is_admin": is_admin(user)}
            if user else None
        ),
        "upload_limit_bytes": upload_limit_for(user),
        "auth_enabled": AUTH0_ENABLED,
        "billing_enabled": STRIPE_ENABLED,
    }


@app.get("/api/admin/stats")
def admin_stats(request: Request):
    """Operator dashboard: user / video / collection counts, hours indexed,
    storage used, and recent signups. Gated by ADMIN_EMAILS."""
    user = current_user(request)
    if not is_admin(user):
        raise HTTPException(403, "admin only")
    from sqlalchemy import func
    with Session(engine) as s:
        users_total = s.scalar(select(func.count()).select_from(User)) or 0
        by_tier = dict(s.execute(
            select(User.tier, func.count()).group_by(User.tier)
        ).all())
        videos_total = s.scalar(select(func.count()).select_from(Video)) or 0
        by_status = dict(s.execute(
            select(Video.status, func.count()).group_by(Video.status)
        ).all())
        total_segments = s.scalar(select(func.coalesce(func.sum(Video.total_segments), 0))) or 0
        collections_total = s.scalar(select(func.count()).select_from(Collection)) or 0
        recent = s.execute(
            select(User.email, User.tier, User.created_at)
            .order_by(User.created_at.desc())
            .limit(10)
        ).all()
        # Activity: total + last 24h + last 7d, per event kind. One query per
        # window — three GROUP BYs over a tiny indexed table.
        now = time.time()
        windows = {"total": None, "d1": now - 86400, "d7": now - 7 * 86400}
        activity = {k: {} for k in ("view", "upload", "search", "qa", "reel")}
        for label, since in windows.items():
            q = select(Event.kind, func.count()).group_by(Event.kind)
            if since is not None:
                q = q.where(Event.at >= since)
            for kind, n in s.execute(q).all():
                if kind in activity:
                    activity[kind][label] = n
        for kind in activity:
            for label in windows:
                activity[kind].setdefault(label, 0)
    bytes_used = 0
    for dirpath, _dirs, files in os.walk(STORAGE):
        for f in files:
            try:
                bytes_used += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return {
        "users": {"total": users_total, "by_tier": by_tier},
        "videos": {
            "total": videos_total,
            "by_status": by_status,
            "hours_indexed": round(total_segments * FRAME_INTERVAL / 3600.0, 1),
        },
        "collections": {"total": collections_total},
        "storage": {"bytes": bytes_used, "gb": round(bytes_used / 1024**3, 2)},
        "activity": activity,
        "recent_signups": [
            {"email": e, "tier": t, "created_at": c} for (e, t, c) in recent
        ],
    }


@app.get("/api/me/library")
def my_library(request: Request):
    """List the signed-in user's own videos and collections."""
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="sign in first")

    coll_map = {}
    videos = []
    for vid, v in VIDEOS.items():
        if v.get("owner") != user.id:
            continue
        cid = v.get("collection_id")
        if cid and cid in COLLECTIONS:
            c = coll_map.get(cid)
            if not c:
                c = {
                    "id": cid,
                    "name": COLLECTIONS[cid]["name"],
                    "total": 0,
                    "indexed": 0,
                    "created": COLLECTIONS[cid].get("created", 0),
                }
                coll_map[cid] = c
            c["total"] += 1
            if v["status"] == "indexed":
                c["indexed"] += 1
        else:
            videos.append(
                {
                    "id": vid,
                    "title": v.get("title", vid),
                    "status": v["status"],
                    "created": v.get("created", 0),
                }
            )

    videos.sort(key=lambda x: x["created"], reverse=True)
    collections = sorted(coll_map.values(), key=lambda c: c["created"], reverse=True)
    return {"collections": collections, "videos": videos}


# ---- Billing (Stripe) ----
class CheckoutRequest(BaseModel):
    tier: str


@app.post("/api/billing/checkout")
def billing_checkout(request: Request, body: CheckoutRequest):
    if not STRIPE_ENABLED:
        raise HTTPException(status_code=503, detail="billing is not configured")
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="sign in first")
    price = TIER_TO_PRICE.get(body.tier)
    if not price:
        raise HTTPException(status_code=400, detail="unknown or unavailable tier")
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=stripe_customer_for(user),
        line_items=[{"price": price, "quantity": 1}],
        client_reference_id=str(user.id),
        success_url=APP_BASE_URL + "/?upgraded=1",
        cancel_url=APP_BASE_URL + "/",
        allow_promotion_codes=True,
    )
    return {"url": session.url}


@app.post("/api/billing/portal")
def billing_portal(request: Request):
    if not STRIPE_ENABLED:
        raise HTTPException(status_code=503, detail="billing is not configured")
    user = current_user(request)
    if not user or not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="no subscription to manage")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=APP_BASE_URL + "/"
    )
    return {"url": session.url}


@app.post("/api/billing/webhook")
async def billing_webhook(request: Request):
    if not (STRIPE_ENABLED and STRIPE_WEBHOOK_SECRET):
        raise HTTPException(status_code=503, detail="billing is not configured")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid signature")

    if event["type"].startswith("customer.subscription."):
        sub = event["data"]["object"]
        items = (sub.get("items") or {}).get("data") or []
        price_id = items[0]["price"]["id"] if items else None
        if event["type"] == "customer.subscription.deleted" or sub.get("status") not in (
            "active",
            "trialing",
        ):
            tier = "free"
        else:
            tier = PRICE_TO_TIER.get(price_id, "free")
        set_tier_by_customer(sub.get("customer"), tier, sub.get("id", ""))
    return {"received": True}


@app.post("/api/upload")
async def upload(
    request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    record_event("upload")
    user = current_user(request)
    cap = upload_limit_for(user)

    # Fast reject via Content-Length before streaming the whole body.
    clen = int(request.headers.get("content-length") or 0)
    if clen and clen > cap:
        raise HTTPException(status_code=413, detail=over_cap_detail(user, cap))

    video_id = uuid.uuid4().hex[:12]
    vdir = STORAGE / video_id
    vdir.mkdir(parents=True, exist_ok=True)

    ext = safe_video_ext(file.filename)
    source = vdir / ("source" + ext)
    total = 0
    with open(source, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:  # backstop in case Content-Length lied / was absent
                out.close()
                shutil.rmtree(vdir, ignore_errors=True)
                raise HTTPException(status_code=413, detail=over_cap_detail(user, cap))
            out.write(chunk)

    VIDEOS[video_id] = {
        "status": "processing",
        "progress": 0,
        "total_segments": 0,
        "error": "",
        "source": str(source),
        "title": file.filename or "Untitled",
        "created": time.time(),
        "owner": user.id if user else None,
    }
    if not user:
        remember_anon_resource(request, "videos", video_id)
    persist_video(video_id)
    background_tasks.add_task(process_video, video_id)
    return {"id": video_id, "status": "processing"}


@app.get("/api/status/{video_id}")
def status(video_id: str, request: Request):
    video = require_video(video_id, request)
    return {
        "status": video["status"],
        "progress": video["progress"],
        "total_segments": video["total_segments"],
        "error": video["error"],
        "title": video["title"],
        "source_url": "/storage/%s/%s" % (video_id, Path(video["source"]).name),
        "summary": video.get("summary", ""),
        "chapters": video.get("chapters", []),
    }


@app.post("/api/search/{video_id}")
def search(video_id: str, req: SearchRequest, request: Request):
    record_event("search")
    video = require_video(video_id, request)
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


class QARequest(BaseModel):
    question: str


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


@app.post("/api/qa/{video_id}")
def video_qa(video_id: str, body: QARequest, request: Request):
    """Answer a question about one video, grounded in its transcript."""
    record_event("qa")
    video = require_video(video_id, request)
    if video["status"] != "indexed":
        raise HTTPException(status_code=409, detail="video is not indexed yet")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="Q&A is not configured")

    context = transcript_context(video_id)
    if not context:
        return {
            "answer": "This video has no transcribed speech, so I can't answer questions about what was said.",
            "has_context": False,
        }

    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        "You are answering a question about a single video using ONLY the "
        "timestamped transcript below. Cite the moments you rely on inline as "
        "a single [Ns] in seconds (one integer, not a range), e.g. 'They discuss "
        "pricing [124s].' Keep it concise. "
        "If the transcript does not contain the answer, say so briefly.\n\n"
        "TRANSCRIPT:\n" + context + "\n\nQUESTION: " + question
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Q&A failed: %s" % exc)
    return {"answer": answer, "has_context": True}


@app.delete("/api/videos/{video_id}")
def delete_endpoint(video_id: str, request: Request):
    if video_id == SAMPLE_ID:
        raise HTTPException(status_code=400, detail="the sample video can't be deleted")
    require_video(video_id, request)  # 404 if missing or not owned
    delete_video(video_id)
    return {"deleted": video_id}


@app.get("/api/videos/{video_id}/source")
def video_source(video_id: str, request: Request):
    """Stream a video's source file (works for in-place library videos too).

    FileResponse honours Range requests, so the <video> element can seek.
    """
    video = require_video(video_id, request)
    src = Path(video["source"])
    if not src.exists():
        raise HTTPException(status_code=404, detail="source file missing")
    return FileResponse(str(src), filename=src.name)


# --------------------------------------------------------------------------
# Library Mode (V2): scan a folder, search across every video in it
# --------------------------------------------------------------------------
class ScanRequest(BaseModel):
    path: str


def _index_collection(video_ids):
    """Index a collection's videos one at a time (CLIP is CPU-bound)."""
    for vid in video_ids:
        if vid in VIDEOS:
            process_video(vid)


@app.post("/api/library/pick")
def library_pick():
    """Open a native folder chooser on the server (local self-host only).

    Browsers never expose a folder's absolute path to JS, so for in-place
    scanning we ask the OS for it directly. macOS via `osascript`; the dialog
    appears on the machine running the server.
    """
    try:
        out = subprocess.run(
            [
                "osascript",
                "-e",
                'POSIX path of (choose folder with prompt "Choose a folder of videos to index")',
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=501, detail="native folder picker is macOS-only")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=501, detail="folder picker unavailable: %s" % exc)

    if out.returncode != 0:
        err = (out.stderr or "").strip()
        if "cancel" in err.lower():  # "User canceled. (-128)"
            return {"path": None, "cancelled": True}
        raise HTTPException(status_code=501, detail=err or "folder picker failed")
    return {"path": out.stdout.strip(), "cancelled": False}


@app.post("/api/library/scan")
def library_scan(body: ScanRequest):
    """Index every video under a local directory, in place (no upload)."""
    root = Path(body.path).expanduser()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail="not a directory: %s" % root)

    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    )
    if not files:
        raise HTTPException(status_code=400, detail="no video files found under %s" % root)

    collection_id = uuid.uuid4().hex[:12]
    video_ids = []
    for f in files:
        vid = uuid.uuid4().hex[:12]
        VIDEOS[vid] = {
            "status": "processing",
            "progress": 0,
            "total_segments": 0,
            "error": "",
            "source": str(f),  # indexed in place — original file, not copied
            "title": f.name,
            "created": time.time(),
            "owner": None,
            "collection_id": collection_id,
        }
        video_ids.append(vid)

    COLLECTIONS[collection_id] = {
        "name": root.name or str(root),
        "path": str(root),
        "video_ids": video_ids,
        "created": time.time(),
    }
    persist_collection(collection_id)
    for vid in video_ids:
        persist_video(vid)
    threading.Thread(target=_index_collection, args=(video_ids,), daemon=True).start()
    print("[scrubless] library scan %s: %d videos" % (root, len(video_ids)))
    return {
        "collection_id": collection_id,
        "name": COLLECTIONS[collection_id]["name"],
        "videos": len(video_ids),
    }


class CreateCollectionRequest(BaseModel):
    name: str = "Uploaded folder"


@app.post("/api/library/create")
def library_create(body: CreateCollectionRequest, request: Request):
    """Create an empty collection (for hosted folder upload)."""
    user = current_user(request)
    collection_id = uuid.uuid4().hex[:12]
    COLLECTIONS[collection_id] = {
        "name": body.name or "Uploaded folder",
        "path": "",  # uploaded, not a server-side path
        "video_ids": [],
        "created": time.time(),
        "owner": user.id if user else None,
    }
    if not user:
        remember_anon_resource(request, "collections", collection_id)
    persist_collection(collection_id)
    return {"collection_id": collection_id, "name": COLLECTIONS[collection_id]["name"]}


@app.post("/api/library/{collection_id}/upload")
async def library_upload(
    collection_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload one video into a collection, then index it (hosted folder mode)."""
    record_event("upload")
    coll = require_collection(collection_id, request)

    user = current_user(request)
    cap = upload_limit_for(user)
    clen = int(request.headers.get("content-length") or 0)
    if clen and clen > cap:
        raise HTTPException(status_code=413, detail=over_cap_detail(user, cap))

    video_id = uuid.uuid4().hex[:12]
    vdir = STORAGE / video_id
    vdir.mkdir(parents=True, exist_ok=True)
    ext = safe_video_ext(file.filename)
    source = vdir / ("source" + ext)
    total = 0
    with open(source, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:  # backstop if Content-Length lied / was absent
                out.close()
                shutil.rmtree(vdir, ignore_errors=True)
                raise HTTPException(status_code=413, detail=over_cap_detail(user, cap))
            out.write(chunk)

    VIDEOS[video_id] = {
        "status": "processing",
        "progress": 0,
        "total_segments": 0,
        "error": "",
        "source": str(source),
        "title": file.filename or "Untitled",
        "created": time.time(),
        "owner": user.id if user else None,
        "collection_id": collection_id,
    }
    coll["video_ids"].append(video_id)
    if not user:
        remember_anon_resource(request, "videos", video_id)
    persist_video(video_id)
    background_tasks.add_task(process_video, video_id)
    return {"id": video_id, "status": "processing"}


@app.get("/api/library/{collection_id}")
def library_status(collection_id: str, request: Request):
    coll = require_collection(collection_id, request)
    videos, indexed = [], 0
    for vid in coll["video_ids"]:
        v = VIDEOS.get(vid)
        if not v:
            continue
        if v["status"] == "indexed":
            indexed += 1
        videos.append(
            {
                "id": vid,
                "title": v["title"],
                "status": v["status"],
                "progress": v["progress"],
            }
        )
    return {
        "collection_id": collection_id,
        "name": coll["name"],
        "path": coll["path"],
        "total": len(coll["video_ids"]),
        "indexed": indexed,
        "videos": videos,
    }


@app.post("/api/library/{collection_id}/search")
def library_search(collection_id: str, req: SearchRequest, request: Request):
    """Search across every indexed video in a collection."""
    record_event("search")
    coll = require_collection(collection_id, request)
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    result = segments.query(
        query_embeddings=[embed_text(query)],
        n_results=40,
        where={"collection_id": collection_id},
    )
    metas = result["metadatas"][0]
    dists = result["distances"][0]

    # Results come back best-first; cap to 3 moments per video so one busy
    # video can't crowd out the rest of the folder.
    results, per_video = [], {}
    for meta, dist in zip(metas, dists):
        vid = meta["video_id"]
        per_video[vid] = per_video.get(vid, 0) + 1
        if per_video[vid] > 3:
            continue
        v = VIDEOS.get(vid, {})
        results.append(
            {
                "video_id": vid,
                "video_title": v.get("title", vid),
                "source_url": "/api/videos/%s/source" % vid,
                "timestamp": meta["timestamp"],
                "frame_url": meta["frame_path"],
                "score": round(1.0 - dist, 4),
                "description": "",
                "transcript_snippet": meta.get("transcript_segment", ""),
            }
        )
        if len(results) >= 12:
            break

    for item in results[:ENRICH_TOP_N]:
        local_path = ROOT / item["frame_url"].lstrip("/")
        item["description"] = describe_frame(local_path)

    return results


@app.post("/api/library/{collection_id}/qa")
def library_qa(collection_id: str, body: QARequest, request: Request):
    """Answer a question across a whole collection, with cited sources that
    map back to a specific video + timestamp."""
    record_event("qa")
    coll = require_collection(collection_id, request)
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="Q&A is not configured")

    # Retrieve the most relevant moments across the whole folder.
    result = segments.query(
        query_embeddings=[embed_text(question)],
        n_results=24,
        where={"collection_id": collection_id},
    )
    metas = (result.get("metadatas") or [[]])[0]
    if not metas:
        return {"answer": "There's nothing indexed in this folder yet.", "sources": []}

    sources, lines = [], []
    for meta in metas:
        vid = meta["video_id"]
        ts = int(meta.get("timestamp", 0))
        title = VIDEOS.get(vid, {}).get("title", vid)
        text = (meta.get("transcript_segment") or "").strip()
        n = len(sources) + 1
        sources.append({"n": n, "video_id": vid, "timestamp": ts, "video_title": title})
        lines.append("[%d] (%s @ %ds) %s" % (n, title, ts, text or "[visual moment, no speech]"))
    context = "\n".join(lines)[:16000]

    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        "You are answering a question about a library of videos using ONLY the "
        "numbered excerpts below (each tagged with its source video and time in "
        "seconds). Cite the excerpts you rely on inline as [n], matching the "
        "numbers. Keep it concise. If the excerpts don't contain the answer, "
        "say so briefly.\n\nEXCERPTS:\n" + context + "\n\nQUESTION: " + question
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Q&A failed: %s" % exc)
    return {"answer": answer, "sources": sources}


# --------------------------------------------------------------------------
# Highlight reels (V3): stitch search-result moments into one clip
# --------------------------------------------------------------------------
REELS = {}  # reel_id -> {status, url, error}


class ReelMoment(BaseModel):
    video_id: str
    timestamp: float


class ReelRequest(BaseModel):
    moments: list[ReelMoment]
    clip_seconds: float = 5.0


def build_reel(reel_id, moments, clip_seconds):
    """Trim `clip_seconds` at each moment, scale to a common 720p frame, concat.

    Video-only (audio dropped) so clips from different sources concat cleanly.
    """
    try:
        inputs, filters, n = [], [], 0
        for m in moments:
            v = VIDEOS.get(m["video_id"])
            if not v or not Path(v["source"]).exists():
                continue
            start = max(0.0, float(m["timestamp"]))
            inputs += ["-ss", "%.2f" % start, "-t", "%.2f" % clip_seconds, "-i", v["source"]]
            filters.append(
                "[%d:v]scale=1280:720:force_original_aspect_ratio=decrease,"
                "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v%d]"
                % (n, n)
            )
            n += 1
        if n == 0:
            raise RuntimeError("no playable moments for this reel")

        concat = "".join("[v%d]" % i for i in range(n)) + "concat=n=%d:v=1:a=0[outv]" % n
        filter_complex = ";".join(filters) + ";" + concat
        out_dir = STORAGE / "reels"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (reel_id + ".mp4")
        cmd = (
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
            + inputs
            + [
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(out),
            ]
        )
        subprocess.run(cmd, check=True)
        REELS.setdefault(reel_id, {}).update(
            status="ready", url="/storage/reels/%s.mp4" % reel_id, error=""
        )
        print("[scrubless] reel %s ready (%d clips)" % (reel_id, n))
    except Exception as exc:  # noqa: BLE001
        REELS.setdefault(reel_id, {}).update(status="error", url="", error=str(exc))
        print("[scrubless] reel %s failed: %s" % (reel_id, exc))


@app.post("/api/reel")
def create_reel(body: ReelRequest, request: Request):
    record_event("reel")
    moments = [{"video_id": m.video_id, "timestamp": m.timestamp} for m in body.moments][:12]
    if not moments:
        raise HTTPException(status_code=400, detail="no moments to build a reel from")
    # Reject reels that mix in any video the caller can't already access — stops
    # an attacker from stitching someone else's footage into their own reel.
    for m in moments:
        if not can_access_video(m["video_id"], request):
            raise HTTPException(status_code=404, detail="video not found")
    user = current_user(request)
    clip_seconds = min(max(body.clip_seconds, 2.0), 10.0)
    reel_id = uuid.uuid4().hex[:12]
    REELS[reel_id] = {
        "status": "building", "url": "", "error": "",
        "owner": user.id if user else None,
    }
    if not user:
        remember_anon_resource(request, "reels", reel_id)
    threading.Thread(
        target=build_reel, args=(reel_id, moments, clip_seconds), daemon=True
    ).start()
    return {"reel_id": reel_id}


@app.get("/api/reel/{reel_id}")
def reel_status(reel_id: str, request: Request):
    if not can_access_reel(reel_id, request):
        raise HTTPException(status_code=404, detail="reel not found")
    return REELS[reel_id]


@app.get("/")
def index():
    record_event("view")
    return FileResponse(str(ROOT / "index.html"))


@app.get("/admin")
def admin_page():
    return FileResponse(str(ROOT / "index.html"))


# Background workers: restore prior state, index the sample, expire old uploads.
restore_state()
threading.Thread(target=ingest_sample, daemon=True).start()
threading.Thread(target=expiry_sweep, daemon=True).start()
