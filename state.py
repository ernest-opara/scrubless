"""Process-local mutable state — these dicts are the in-memory truth restored
from the DB at boot and mirrored back via persist_*. Single-instance only."""

SAMPLE_ID = "sample"

# video_id -> {status, progress, total_segments, error, source, title, owner, ...}
VIDEOS = {}

# collection_id -> {name, path, video_ids, created, owner}
COLLECTIONS = {}

# reel_id -> {status, url, error, owner}
REELS = {}
