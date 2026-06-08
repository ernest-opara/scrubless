"""Stripe init + checkout / portal / webhook + tier helpers used by uploads."""
import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import current_user
from config import (
    ANON_LIMIT,
    APP_BASE_URL,
    MB,
    PRICE_TO_TIER,
    STRIPE_ENABLED,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    TIER_LIMITS,
    TIER_TO_PRICE,
)
from models import User, engine

if STRIPE_ENABLED:
    stripe.api_key = STRIPE_SECRET_KEY
    print("[scrubless] Stripe billing enabled")
else:
    print("[scrubless] Stripe not configured — all accounts stay free")


def upload_limit_for(user):
    return TIER_LIMITS.get(user.tier, ANON_LIMIT) if user else ANON_LIMIT


def over_cap_detail(user, cap):
    mb = cap // MB
    if user is None:
        return "Files over %dMB need an account — sign in to upload larger videos." % mb
    return "Your %s plan allows up to %dMB — upgrade for larger uploads." % (user.tier, mb)


def stripe_customer_for(user):
    """Return the user's Stripe customer id, creating one if needed."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    cust = stripe.Customer.create(
        email=user.email or None, metadata={"user_id": str(user.id)}
    )
    with Session(engine) as s:
        u = s.get(User, user.id)
        u.stripe_customer_id = cust.id
        s.commit()
    return cust.id


def set_tier_by_customer(customer_id, tier, sub_id=""):
    """Update a user's tier from a Stripe webhook, keyed by customer id."""
    if not customer_id:
        return
    with Session(engine) as s:
        u = s.scalar(select(User).where(User.stripe_customer_id == customer_id))
        if u:
            u.tier = tier
            u.stripe_subscription_id = sub_id or ""
            s.commit()
            print("[scrubless] billing: %s -> %s" % (u.email, tier))


class CheckoutRequest(BaseModel):
    tier: str


router = APIRouter()


@router.post("/api/billing/checkout")
def billing_checkout(request: Request, body: CheckoutRequest):
    if not STRIPE_ENABLED:
        raise HTTPException(status_code=503, detail="billing is not configured")
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="sign in first")
    price = TIER_TO_PRICE.get(body.tier)
    if not price:
        raise HTTPException(status_code=400, detail="unknown or unavailable tier")
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=stripe_customer_for(user),
        line_items=[{"price": price, "quantity": 1}],
        client_reference_id=str(user.id),
        success_url=APP_BASE_URL + "/?upgraded=1",
        cancel_url=APP_BASE_URL + "/",
        allow_promotion_codes=True,
    )
    return {"url": session.url}


@router.post("/api/billing/portal")
def billing_portal(request: Request):
    if not STRIPE_ENABLED:
        raise HTTPException(status_code=503, detail="billing is not configured")
    user = current_user(request)
    if not user or not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="no subscription to manage")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=APP_BASE_URL + "/"
    )
    return {"url": session.url}


@router.post("/api/billing/webhook")
async def billing_webhook(request: Request):
    if not (STRIPE_ENABLED and STRIPE_WEBHOOK_SECRET):
        raise HTTPException(status_code=503, detail="billing is not configured")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid signature")

    if event["type"].startswith("customer.subscription."):
        sub = event["data"]["object"]
        items = (sub.get("items") or {}).get("data") or []
        price_id = items[0]["price"]["id"] if items else None
        if event["type"] == "customer.subscription.deleted" or sub.get("status") not in (
            "active",
            "trialing",
        ):
            tier = "free"
        else:
            tier = PRICE_TO_TIER.get(price_id, "free")
        set_tier_by_customer(sub.get("customer"), tier, sub.get("id", ""))
    return {"received": True}
