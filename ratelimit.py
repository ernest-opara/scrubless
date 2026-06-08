"""The single Limiter instance, shared so all route modules decorate against
the same object the app registers as `app.state.limiter`."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
