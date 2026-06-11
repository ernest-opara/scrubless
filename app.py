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
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline' https://js.stripe.com; "
            "connect-src 'self' https://api.stripe.com; "
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


# Hosts we collapse onto a short label for the admin "Top sources" panel —
# anything not in this map shows up as its bare hostname.
_SOURCE_ALIASES = {
    "t.co": "twitter", "twitter.com": "twitter", "x.com": "twitter",
    "news.ycombinator.com": "hn",
    "producthunt.com": "producthunt", "www.producthunt.com": "producthunt",
    "linkedin.com": "linkedin", "www.linkedin.com": "linkedin", "lnkd.in": "linkedin",
    "reddit.com": "reddit", "www.reddit.com": "reddit", "old.reddit.com": "reddit",
    "google.com": "google", "www.google.com": "google",
    "bing.com": "bing", "duckduckgo.com": "duckduckgo",
    "facebook.com": "facebook", "www.facebook.com": "facebook", "m.facebook.com": "facebook",
    "youtube.com": "youtube", "www.youtube.com": "youtube",
    "instagram.com": "instagram", "github.com": "github",
}


def request_source(request: Request) -> str:
    """Best-effort traffic attribution for a landing-page view.
    Order: explicit ?utm_source= (wins) → Referer hostname (normalized) →
    `direct`. Same-host referers collapse to `internal` so the admin panel
    can filter our own navigation back out."""
    from urllib.parse import urlparse

    utm = (request.query_params.get("utm_source") or "").strip().lower()[:32]
    if utm:
        return "utm:" + utm
    ref = request.headers.get("referer") or ""
    if not ref:
        return "direct"
    try:
        host = (urlparse(ref).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return "direct"
    if not host:
        return "direct"
    our_host = (urlparse(config.APP_BASE_URL).hostname or "").lower()
    if our_host and (host == our_host or host.endswith("." + our_host)):
        return "internal"
    return _SOURCE_ALIASES.get(host, host)[:64]


_CANONICAL_HOST = "https://www.getscrubless.com"
_ROBOTS_TXT = (
    "User-agent: *\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin\n"
    "Disallow: /storage/\n"
    "Sitemap: " + _CANONICAL_HOST + "/sitemap.xml\n"
)
_SITEMAP_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    "  <url>\n"
    "    <loc>" + _CANONICAL_HOST + "/</loc>\n"
    "    <changefreq>weekly</changefreq>\n"
    "    <priority>1.0</priority>\n"
    "  </url>\n"
    "</urlset>\n"
)


@app.get("/robots.txt")
def robots_txt():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(_ROBOTS_TXT)


@app.get("/sitemap.xml")
def sitemap_xml():
    from fastapi.responses import Response
    return Response(content=_SITEMAP_XML, media_type="application/xml")


@app.get("/")
def index(request: Request):
    record_event("view", source=request_source(request))
    return FileResponse(str(config.ROOT / "index.html"))


# Background workers: restore prior state, index the sample, expire old uploads.
indexing.restore_state()
threading.Thread(target=indexing.ingest_sample, daemon=True).start()
threading.Thread(target=indexing.expiry_sweep, daemon=True).start()
