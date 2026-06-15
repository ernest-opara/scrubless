"""Library (folder) routes: pick / scan / create / upload / status / my-library."""
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from access import (
    remember_anon_resource,
    require_collection,
    require_localhost,
    safe_video_ext,
)
from auth import current_user
from billing import over_cap_detail, upload_limit_for
from config import STORAGE, VIDEO_EXTS
from geo import request_country
from indexing import process_video
from models import persist_collection, persist_video, record_event
from ratelimit import limiter
from state import COLLECTIONS, VIDEOS
from usage import require_indexing_within_cap


class ScanRequest(BaseModel):
    path: str


class CreateCollectionRequest(BaseModel):
    name: str = "Uploaded folder"


def _index_collection(video_ids):
    """Index a collection's videos one at a time (CLIP is CPU-bound)."""
    for vid in video_ids:
        if vid in VIDEOS:
            process_video(vid)


router = APIRouter()


@router.post("/api/library/pick")
def library_pick(request: Request):
    """Open a native folder chooser on the server (local self-host only).

    Browsers never expose a folder's absolute path to JS, so for in-place
    scanning we ask the OS for it directly. macOS via `osascript`; the dialog
    appears on the machine running the server.
    """
    require_localhost(request)
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


@router.post("/api/library/scan")
def library_scan(body: ScanRequest, request: Request):
    """Index every video under a local directory, in place (no upload)."""
    require_localhost(request)
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


@router.post("/api/library/create")
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


@router.post("/api/library/{collection_id}/upload")
@limiter.limit("60/hour")
async def library_upload(
    collection_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload one video into a collection, then index it (hosted folder mode)."""
    user = current_user(request)
    require_indexing_within_cap(user)
    record_event("upload", user_id=user.id if user else None, country=request_country(request))
    coll = require_collection(collection_id, request)

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


@router.get("/api/library/{collection_id}")
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


@router.get("/api/me/library")
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
