"""Single-video routes: upload, status, delete, source streaming."""
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from access import remember_anon_resource, require_video, safe_video_ext
from auth import current_user
from billing import over_cap_detail, upload_limit_for
from config import STORAGE
from geo import request_country
from indexing import delete_video, process_video
from models import persist_video, record_event
from ratelimit import limiter
from state import SAMPLE_ID, VIDEOS
from usage import require_indexing_within_cap

router = APIRouter()


@router.post("/api/upload")
@limiter.limit("20/hour")
async def upload(
    request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    user = current_user(request)
    require_indexing_within_cap(user)
    record_event("upload", user_id=user.id if user else None, country=request_country(request))
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


@router.get("/api/status/{video_id}")
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


@router.delete("/api/videos/{video_id}")
def delete_endpoint(video_id: str, request: Request):
    if video_id == SAMPLE_ID:
        raise HTTPException(status_code=400, detail="the sample video can't be deleted")
    require_video(video_id, request)  # 404 if missing or not owned
    delete_video(video_id)
    return {"deleted": video_id}


@router.get("/api/videos/{video_id}/source")
def video_source(video_id: str, request: Request):
    """Stream a video's source file (works for in-place library videos too).
    FileResponse honours Range requests, so the <video> element can seek."""
    video = require_video(video_id, request)
    src = Path(video["source"])
    if not src.exists():
        raise HTTPException(status_code=404, detail="source file missing")
    return FileResponse(str(src), filename=src.name)
