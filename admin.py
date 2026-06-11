"""Admin dashboard: stats endpoint + the /admin SPA route."""
import os
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import current_user, is_admin
from config import FRAME_INTERVAL, ROOT, STORAGE
from models import Collection, Event, User, Video, engine

router = APIRouter()


@router.get("/api/admin/stats")
def admin_stats(request: Request):
    """Operator dashboard: user / video / collection counts, hours indexed,
    storage used, activity series + recent signups. Gated by ADMIN_EMAILS."""
    user = current_user(request)
    if not is_admin(user):
        raise HTTPException(403, "admin only")
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
        kinds = ("view", "upload", "search", "qa", "reel")
        activity = {k: {} for k in kinds}
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
        # 7-day series per kind: bucket every 7d event into a 0..6 slot where 6
        # is the last 24h and 0 is the 7..6-days-ago window.
        for kind in kinds:
            activity[kind]["series"] = [0] * 7
        rows = s.execute(
            select(Event.kind, Event.at).where(Event.at >= windows["d7"])
        ).all()
        for kind, at in rows:
            if kind not in activity:
                continue
            slot = 6 - int((now - at) // 86400)
            if 0 <= slot <= 6:
                activity[kind]["series"][slot] += 1
        series_starts_at = windows["d7"]  # epoch seconds of slot 0 (oldest)

        # Traffic sources: aggregate the `source` column on view events for
        # total / last 24 h / last 7 d. Internal navigation is split out so the
        # admin panel can default to 7 d external traffic while leaving the
        # all-time view a click away. Pre-migration rows have source=NULL
        # and are skipped.
        traffic_by_window = {}
        for label, since in windows.items():
            q = select(Event.source, func.count()).where(
                Event.kind == "view", Event.source.is_not(None)
            )
            if since is not None:
                q = q.where(Event.at >= since)
            rows = s.execute(q.group_by(Event.source)).all()
            ext, internal_n = [], 0
            for src, n in rows:
                if src == "internal":
                    internal_n = n
                else:
                    ext.append({"source": src, "count": n})
            ext.sort(key=lambda r: r["count"], reverse=True)
            traffic_by_window[label] = {
                "top_sources": ext[:10],
                "external_total": sum(r["count"] for r in ext),
                "internal_views": internal_n,
            }
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
        "series_starts_at": series_starts_at,
        "traffic": traffic_by_window,
        "recent_signups": [
            {"email": e, "tier": t, "created_at": c} for (e, t, c) in recent
        ],
    }


@router.get("/admin")
def admin_page():
    return FileResponse(str(ROOT / "index.html"))
