"""Highlight reels: stitch search-result moments into one clip."""
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from access import can_access_reel, can_access_video, remember_anon_resource
from auth import current_user
from config import STORAGE
from models import record_event
from ratelimit import limiter
from state import REELS, VIDEOS


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


router = APIRouter()


@router.post("/api/reel")
@limiter.limit("10/hour")
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


@router.get("/api/reel/{reel_id}")
def reel_status(reel_id: str, request: Request):
    if not can_access_reel(reel_id, request):
        raise HTTPException(status_code=404, detail="reel not found")
    return REELS[reel_id]
