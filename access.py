"""Ownership / access gates + the gated /storage route that replaces the public
static mount. Imports auth + state; do not import routes from here."""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from auth import current_user, is_admin
from config import STORAGE, VIDEO_EXTS
from state import COLLECTIONS, REELS, SAMPLE_ID, VIDEOS


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


def require_localhost(request: Request):
    """Allow only loopback callers. Used to gate endpoints that touch the host
    filesystem (scan, pick) so they're usable in local self-host but inert on
    a public deploy."""
    host = (request.client.host if request.client else "") or ""
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=404, detail="not found")


def safe_video_ext(filename: str) -> str:
    """Return a safe video extension from a user-supplied filename, or .mp4.
    Refusing non-video extensions prevents serving an attacker's .html/.svg
    from our own origin via the storage route (stored-XSS)."""
    ext = Path(filename or "").suffix.lower()
    return ext if ext in VIDEO_EXTS else ".mp4"


router = APIRouter()


@router.get("/storage/{rest:path}")
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
