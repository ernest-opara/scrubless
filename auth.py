"""Auth0 login / sessions / current_user / is_admin. Plus the /api/auth/* router."""
import time

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import (
    ADMIN_EMAILS,
    APP_BASE_URL,
    AUTH0_CLIENT_ID,
    AUTH0_CLIENT_SECRET,
    AUTH0_DOMAIN,
    AUTH0_ENABLED,
)
from models import User, engine
from ratelimit import limiter

oauth = OAuth()
if AUTH0_ENABLED:
    oauth.register(
        "auth0",
        client_id=AUTH0_CLIENT_ID,
        client_secret=AUTH0_CLIENT_SECRET,
        client_kwargs={"scope": "openid profile email"},
        server_metadata_url="https://%s/.well-known/openid-configuration" % AUTH0_DOMAIN,
    )
    print("[scrubless] Auth0 login enabled")
else:
    print("[scrubless] Auth0 not configured — anonymous uploads only (<=500MB)")


def current_user(request: Request):
    """Return the logged-in User, or None."""
    uid = request.session.get("user_id")
    if not uid:
        return None
    with Session(engine) as s:
        return s.get(User, uid)


def is_admin(user):
    return bool(user and user.email and user.email.lower() in ADMIN_EMAILS)


router = APIRouter()


@router.get("/api/auth/login")
@limiter.limit("20/minute")
async def auth_login(request: Request):
    if not AUTH0_ENABLED:
        raise HTTPException(status_code=503, detail="login is not configured")
    return await oauth.auth0.authorize_redirect(request, APP_BASE_URL + "/api/auth/callback")


@router.get("/api/auth/callback")
async def auth_callback(request: Request):
    if not AUTH0_ENABLED:
        raise HTTPException(status_code=503, detail="login is not configured")
    token = await oauth.auth0.authorize_access_token(request)
    info = token.get("userinfo") or {}
    sub = info.get("sub")
    email = (info.get("email") or "").lower()
    if not sub:
        raise HTTPException(status_code=400, detail="no identity returned")
    with Session(engine) as s:
        user = s.scalar(select(User).where(User.auth0_sub == sub))
        if user is None:
            user = User(auth0_sub=sub, email=email, tier="free", created_at=time.time())
            s.add(user)
            s.commit()
            s.refresh(user)
        elif email and user.email != email:
            user.email = email
            s.commit()
        request.session["user_id"] = user.id
    return RedirectResponse("/")


@router.get("/api/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    if AUTH0_ENABLED:
        return RedirectResponse(
            "https://%s/v2/logout?client_id=%s&returnTo=%s"
            % (AUTH0_DOMAIN, AUTH0_CLIENT_ID, APP_BASE_URL + "/")
        )
    return RedirectResponse("/")


@router.get("/api/auth/me")
def auth_me(request: Request):
    # Imported here to avoid a circular import (billing imports auth).
    from billing import upload_limit_for
    from config import ANNUAL_ENABLED, AUTH0_ENABLED as ae, STRIPE_ENABLED
    from usage import usage_summary

    user = current_user(request)
    return {
        "user": (
            {"email": user.email, "tier": user.tier, "is_admin": is_admin(user)}
            if user else None
        ),
        "upload_limit_bytes": upload_limit_for(user),
        "auth_enabled": ae,
        "billing_enabled": STRIPE_ENABLED,
        "annual_enabled": ANNUAL_ENABLED,
        "usage": usage_summary(user),
    }
