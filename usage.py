"""Per-user monthly usage helpers — counts what a signed-in user has done
in the current calendar month, used by the routes to enforce TIER_CAPS.

Admins (is_admin) and users on a cap-less tier (Team) get a free pass.
Anonymous users aren't gated here (their hard floor is the upload-size cap
and the 24h auto-expiry); Q&A is gated to signed-in users separately."""
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import is_admin
from config import FRAME_INTERVAL, TIER_CAPS
from models import Event, Video, engine


def _month_start_epoch() -> float:
    """Epoch seconds of the first instant of the current UTC month."""
    now = datetime.now(timezone.utc)
    first = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return first.timestamp()


def _cap_for(user, key: str):
    """Look up a TIER_CAPS value for the user's tier, or None for no cap."""
    if user is None:
        return TIER_CAPS["free"].get(key)
    if is_admin(user):
        return None
    return TIER_CAPS.get(user.tier or "free", TIER_CAPS["free"]).get(key)


def qa_used_this_month(user) -> int:
    if user is None:
        return 0
    since = _month_start_epoch()
    with Session(engine) as s:
        return (
            s.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.kind == "qa", Event.user_id == user.id, Event.at >= since)
            )
            or 0
        )


def hours_indexed_this_month(user) -> float:
    """Sum of indexed video durations (total_segments × FRAME_INTERVAL) for
    every video the user owns that was created in the current month."""
    if user is None:
        return 0.0
    since = _month_start_epoch()
    with Session(engine) as s:
        seconds = s.scalar(
            select(func.coalesce(func.sum(Video.total_segments), 0) * FRAME_INTERVAL).where(
                Video.owner == user.id, Video.created >= since
            )
        ) or 0
    return seconds / 3600.0


def require_qa_within_cap(user):
    """Raise 402 if the user is over their monthly Q&A cap. No-op for None,
    admins, and cap-less tiers."""
    cap = _cap_for(user, "qa_per_month")
    if cap is None or user is None:
        return
    used = qa_used_this_month(user)
    if used >= cap:
        raise HTTPException(
            status_code=402,
            detail=(
                "Monthly Q&A limit reached (%d / %d on the %s plan). "
                "Upgrade your plan or wait until next month."
                % (used, cap, user.tier or "free")
            ),
        )


def require_indexing_within_cap(user):
    """Raise 402 if the user is already over their monthly hours-indexed cap.
    Soft cap: lets the in-progress upload through, blocks the next one."""
    cap = _cap_for(user, "hours_indexed")
    if cap is None or user is None:
        return
    used = hours_indexed_this_month(user)
    if used >= cap:
        raise HTTPException(
            status_code=402,
            detail=(
                "Monthly indexing limit reached (%.1f / %d hr on the %s plan). "
                "Upgrade your plan or wait until next month."
                % (used, cap, user.tier or "free")
            ),
        )


def usage_summary(user) -> dict:
    """Compact dict for /api/auth/me — lets the SPA show progress bars."""
    if user is None:
        return {}
    qa_cap = _cap_for(user, "qa_per_month")
    h_cap = _cap_for(user, "hours_indexed")
    return {
        "month_started_at": _month_start_epoch(),
        "qa": {"used": qa_used_this_month(user), "cap": qa_cap},
        "hours_indexed": {
            "used": round(hours_indexed_this_month(user), 2),
            "cap": h_cap,
        },
    }
