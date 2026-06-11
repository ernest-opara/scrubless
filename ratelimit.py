"""The single Limiter instance, shared so all route modules decorate against
the same object the app registers as `app.state.limiter`.

On Railway (and most reverse-proxy hosts) `request.client.host` is the proxy's
internal IP — every request from one visitor lands on a different bucket and
the limits are effectively disabled. We key off the first entry of
`X-Forwarded-For` instead, falling back to `request.client.host` for local
development where no proxy is in front."""
from slowapi import Limiter


def client_ip(request) -> str:
    xff = request.headers.get("x-forwarded-for") or ""
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return (request.client.host if request.client else "") or "unknown"


limiter = Limiter(key_func=client_ip)
