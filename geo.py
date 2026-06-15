"""Resolve a request's country from CDN-forwarded headers.

We do NOT bundle a GeoIP database. Until a CDN (Cloudflare, Vercel, Fly,
CloudFront) sits in front of the app and forwards the country header,
events stay "unknown". Adding Cloudflare in front (free) instantly lights
up the geo panels on /admin.
"""
from fastapi import Request

# Header preference order. Cloudflare first since it's the most common
# free option; the others let us survive a host migration without code
# changes.
_COUNTRY_HEADERS = (
    "cf-ipcountry",
    "x-vercel-ip-country",
    "x-country-code",
    "fly-client-country",
    "cloudfront-viewer-country",
)
# Some CDNs return these when they can't resolve the IP. "EU" is intentional
# noise we don't want to claim as a real country either.
_BAD_COUNTRY = {"", "XX", "T1", "ZZ", "EU"}


def request_country(request: Request):
    """ISO-3166-1 alpha-2 (uppercase) if a CDN header is present and valid;
    None otherwise."""
    for h in _COUNTRY_HEADERS:
        v = request.headers.get(h)
        if v:
            v = v.strip().upper()
            if len(v) == 2 and v.isalpha() and v not in _BAD_COUNTRY:
                return v
    return None
