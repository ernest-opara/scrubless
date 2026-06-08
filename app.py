"""Scrubless — semantic video search. Thin entry: FastAPI setup + router wiring.

All real logic lives in sibling modules (config, models, state, embeddings,
auth, access, billing, indexing, videos, library, search, reels, admin).
Run:  uvicorn app:app --port 8080
"""
import threading

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

import config

# Refuse to boot on HTTPS with the default / short SESSION_SECRET — a known
# secret means forgeable session cookies. Check before the heavy imports.
if config.IS_HTTPS and (
    config.SESSION_SECRET == "dev-insecure-change-me" or len(config.SESSION_SECRET) < 32
):
    raise RuntimeError(
        "SESSION_SECRET (or AUTH0_SECRET) must be a strong (>=32 char) random "
        "value when APP_BASE_URL is https. Refusing to start."
    )

import indexing  # noqa: E402 — triggers CLIP load + DB migrations; intentionally after the guard
from models import record_event  # noqa: E402
from ratelimit import limiter  # noqa: E402

app = FastAPI(title="Scrubless")

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    https_only=config.IS_HTTPS,
    same_site="lax",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers(request, call_next):
    """Defensive headers on every response: stop content-type sniffing, deny
    framing, leak less in referrers, and (on HTTPS) enable HSTS. CSP is set
    only on HTML so it doesn't break ranged video streaming from /storage."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if config.IS_HTTPS:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    if (response.headers.get("content-type") or "").startswith("text/html"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' "
            "https://js.stripe.com; connect-src 'self' https://api.stripe.com; "
            "frame-src https://js.stripe.com https://hooks.stripe.com; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self' "
            "https://*.auth0.com https://checkout.stripe.com",
        )
    return response


# Static-mount only the public mascot. Storage is gated by access.storage_serve
# so an uploader's videos / frames are only visible to the uploader.
app.mount("/scrubby", StaticFiles(directory=str(config.ROOT / "scrubby")), name="scrubby")

# Routers — order doesn't matter for routing but mirrors the module list.
import access, admin, auth, billing, library, reels, search, videos  # noqa: E402

for r in (
    auth.router,
    access.router,
    billing.router,
    videos.router,
    library.router,
    search.router,
    reels.router,
    admin.router,
):
    app.include_router(r)


@app.get("/")
def index():
    record_event("view")
    return FileResponse(str(config.ROOT / "index.html"))


# Background workers: restore prior state, index the sample, expire old uploads.
indexing.restore_state()
threading.Thread(target=indexing.ingest_sample, daemon=True).start()
threading.Thread(target=indexing.expiry_sweep, daemon=True).start()
