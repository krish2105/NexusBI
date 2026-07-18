"""Billing — Stripe checkout / portal / webhook (Phase 3).

Entirely env-gated: with no ``STRIPE_SECRET_KEY`` + ``STRIPE_PRICE_PRO`` the
endpoints report ``enabled: false`` and everyone stays on Free (all features
work — the free tier is the product, not a teaser). Stripe **test mode** is free,
so this whole flow can be exercised at $0.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_current_user
from app.config import settings
from app.db.app_store import get_store

router = APIRouter(prefix="/billing", tags=["billing"])


def _stripe():
    import stripe  # lazy: only imported when billing is configured

    stripe.api_key = settings.stripe_secret_key
    return stripe


def _require(user: dict | None) -> dict:
    if not user:
        raise HTTPException(401, "authentication required")
    return user


@router.get("/config")
def config():
    """What the frontend needs to render pricing without secrets."""
    return {"enabled": settings.billing_enabled,
            "publishable_key": settings.stripe_publishable_key}


@router.post("/checkout")
def checkout(user: dict | None = Depends(get_current_user)):
    """Start a Stripe Checkout for the Pro plan; returns the hosted-page URL."""
    user = _require(user)
    if not settings.billing_enabled:
        return {"enabled": False,
                "detail": "billing is not configured on this deployment"}
    store = get_store()
    full = store.get_user(user["id"])
    stripe = _stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_pro, "quantity": 1}],
        customer_email=full["email"],
        client_reference_id=user["id"],
        success_url=f"{settings.app_base_url}/account?upgraded=1",
        cancel_url=f"{settings.app_base_url}/pricing",
        allow_promotion_codes=True,
    )
    return {"enabled": True, "url": session.url}


@router.post("/portal")
def portal(user: dict | None = Depends(get_current_user)):
    """Stripe customer portal (manage / cancel the subscription)."""
    user = _require(user)
    if not settings.billing_enabled:
        return {"enabled": False}
    full = get_store().get_user(user["id"])
    customer = full.get("stripe_customer_id")
    if not customer:
        raise HTTPException(400, "no billing account yet — upgrade first")
    stripe = _stripe()
    session = stripe.billing_portal.Session.create(
        customer=customer, return_url=f"{settings.app_base_url}/account")
    return {"url": session.url}


@router.post("/webhook")
async def webhook(request: Request):
    """Stripe -> us: apply plan changes. Signature-verified; no auth (Stripe calls
    it). No-op when billing is disabled."""
    if not settings.billing_enabled or not settings.stripe_webhook_secret:
        return {"ok": True, "ignored": "billing disabled"}
    stripe = _stripe()
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret)
    except Exception:  # noqa: BLE001 - bad signature or malformed
        raise HTTPException(400, "invalid webhook signature")

    store = get_store()
    etype = event["type"]
    obj = event["data"]["object"]
    if etype == "checkout.session.completed":
        uid = obj.get("client_reference_id")
        if uid:
            store.set_plan(uid, "pro", stripe_customer_id=obj.get("customer"))
            store.append_audit("billing.upgraded", actor=uid, verdict="ALLOW")
    elif etype in ("customer.subscription.deleted",
                   "customer.subscription.canceled"):
        u = store.get_user_by_stripe_customer(obj.get("customer"))
        if u:
            store.set_plan(u["id"], "free")
            store.append_audit("billing.downgraded", actor=u["id"], verdict="ALLOW")
    return {"ok": True}
