"""Configuration: env vars, paths, and constants. No siblings depend on each
other through here — this module imports nothing from the rest of the app."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
STORAGE = ROOT / "storage"
STORAGE.mkdir(exist_ok=True)

FRAME_INTERVAL = 5  # seconds between extracted frames
ENRICH_TOP_N = 3  # how many top results get a Claude Vision description

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# Comma-separated emails (case-insensitive) allowed into /admin.
ADMIN_EMAILS = {
    e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
}

# Auth (Auth0) + sessions + database
SESSION_SECRET = (
    os.getenv("SESSION_SECRET")
    or os.getenv("AUTH0_SECRET")  # the name Auth0's quickstart generates
    or "dev-insecure-change-me"
)
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8080").rstrip("/")
IS_HTTPS = APP_BASE_URL.startswith("https://")

AUTH0_DOMAIN = (
    os.getenv("AUTH0_DOMAIN", "")
    .strip()
    .removeprefix("https://")
    .removeprefix("http://")
    .rstrip("/")
)  # tolerate a pasted scheme/trailing slash
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "").strip()
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET", "").strip()
AUTH0_ENABLED = bool(AUTH0_DOMAIN and AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + str(ROOT / "scrubless.db"))
if DATABASE_URL.startswith("postgres://"):  # Railway sometimes uses the old scheme
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Per-tier upload caps (bytes). Anonymous == free; paid tiers raise the cap.
MB = 1024 * 1024
GB = 1024 * MB
ANON_LIMIT = 500 * MB
# Per-file upload caps by tier. Free is anon + signed-in-free; team gets the
# largest single-file cap because team-scale footage tends to be high-bitrate.
TIER_LIMITS = {
    "free": 500 * MB,
    "pro": 2 * GB,
    "studio": 10 * GB,
    "team": 25 * GB,
}
# Admins (ADMIN_EMAILS) ignore the tier ladder — set well above any realistic
# single file but bounded so a runaway test can't fill the volume by accident.
ADMIN_LIMIT = 100 * GB

# Monthly usage caps per tier. `hours_indexed` is hours of video processed in
# the current calendar month; `qa_per_month` is the count of Q&A requests in
# the same window. None = unlimited. Enforced at the relevant route entry.
TIER_CAPS = {
    "free":   {"hours_indexed":   2, "qa_per_month":   10},
    "pro":    {"hours_indexed":  20, "qa_per_month":  200},
    "studio": {"hours_indexed": 100, "qa_per_month": 1000},
    "team":   {"hours_indexed": None, "qa_per_month": None},
}

# Stripe billing
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
# Monthly prices (always required for paid tiers).
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "").strip()
STRIPE_PRICE_STUDIO = os.getenv("STRIPE_PRICE_STUDIO", "").strip()
STRIPE_PRICE_TEAM = os.getenv("STRIPE_PRICE_TEAM", "").strip()
# Annual prices — optional. Set these to enable the "annual" toggle on the
# pricing page; without them the toggle still renders but defaults to monthly.
STRIPE_PRICE_PRO_YEARLY = os.getenv("STRIPE_PRICE_PRO_YEARLY", "").strip()
STRIPE_PRICE_STUDIO_YEARLY = os.getenv("STRIPE_PRICE_STUDIO_YEARLY", "").strip()
STRIPE_PRICE_TEAM_YEARLY = os.getenv("STRIPE_PRICE_TEAM_YEARLY", "").strip()

TIER_TO_PRICE = {
    "pro": STRIPE_PRICE_PRO,
    "studio": STRIPE_PRICE_STUDIO,
    "team": STRIPE_PRICE_TEAM,
}
TIER_TO_PRICE_YEARLY = {
    "pro": STRIPE_PRICE_PRO_YEARLY,
    "studio": STRIPE_PRICE_STUDIO_YEARLY,
    "team": STRIPE_PRICE_TEAM_YEARLY,
}
# Reverse lookups so webhook can resolve which tier a Stripe price id belongs to.
PRICE_TO_TIER = {p: t for t, p in TIER_TO_PRICE.items() if p}
PRICE_TO_TIER.update({p: t for t, p in TIER_TO_PRICE_YEARLY.items() if p})
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY)
ANNUAL_ENABLED = bool(
    STRIPE_PRICE_PRO_YEARLY or STRIPE_PRICE_STUDIO_YEARLY or STRIPE_PRICE_TEAM_YEARLY
)

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv"}
VIDEO_TTL_SECONDS = 24 * 3600  # free uploads auto-expire after 24h
