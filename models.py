"""SQLAlchemy models + the persistence helpers that mirror in-memory state to
the DB. Importing this module creates tables and runs additive migrations."""
import json
import time
from typing import Optional

from sqlalchemy import Float, String, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from config import DATABASE_URL
from state import COLLECTIONS, SAMPLE_ID, VIDEOS


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
    # ISO-3166-1 alpha-2 (e.g. "US", "GB"). Set at signup from a CDN header.
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, default=None)


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
    Q&A, upload, and reel writes one row. Aggregated by kind + time window.
    `source` is set on view events: a normalized referer / UTM tag (twitter,
    hn, producthunt, direct, internal, etc.); NULL on other event kinds.
    `user_id` is set on signed-in usage events (qa, search, upload, reel) so
    monthly per-user caps can be enforced; NULL for anonymous or view events."""

    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True, default=None, index=True)
    # ISO-3166-1 alpha-2. NULL until Cloudflare/Vercel/Fly is fronting the app
    # and a CDN country header is forwarded; pre-migration rows are also NULL.
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, default=None, index=True)


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
        "events": {
            "source": "VARCHAR(64) DEFAULT NULL",
            "user_id": "INTEGER DEFAULT NULL",
            "country": "VARCHAR(2) DEFAULT NULL",
        },
        "users": {"country": "VARCHAR(2) DEFAULT NULL"},
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


# --------------------------------------------------------------------------
# Persistence: mirror the VIDEOS/COLLECTIONS dicts into the DB so a restart
# (e.g. a Railway redeploy) doesn't lose the library.
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


def record_event(kind, source=None, user_id=None, country=None):
    """Fire-and-forget activity log; never block a request on a tracking write.
    `source` is recorded on view events for traffic attribution.
    `user_id` is recorded on usage events (qa, search, upload, reel) for
    per-user monthly cap enforcement; None for anonymous or view events.
    `country` is the ISO-3166-1 alpha-2 from a CDN header; None when unknown."""
    try:
        with Session(engine) as s:
            s.add(Event(
                kind=kind, at=time.time(), source=source,
                user_id=user_id, country=country,
            ))
            s.commit()
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] record_event %s failed: %s" % (kind, exc))
