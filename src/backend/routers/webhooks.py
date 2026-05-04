"""Stripe webhook handler for FinSight subscription lifecycle events.

This endpoint is called directly by Stripe — not by the frontend.
Every inbound request is verified using the ``Stripe-Signature`` header
and the ``STRIPE_WEBHOOK_SECRET`` environment variable to ensure the
payload was not tampered with.

Handled events
--------------
- ``checkout.session.completed``     — upgrade user to ``paid`` (matches Checkout customer to DB user)
- ``invoice.payment_succeeded``      — same upgrade path (covers renewals / if only invoice is configured)
- ``customer.subscription.deleted``  — downgrade user to ``free``, revoke API keys

Environment variables required
------------------------------
- ``STRIPE_SECRET_KEY``     — Stripe secret key (``sk_live_…`` or ``sk_test_…``)
- ``STRIPE_WEBHOOK_SECRET`` — Signing secret from the Stripe dashboard webhook endpoint
"""

import os

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from auth.password import generate_api_key
from database import SessionLocal
from models import APIKey, User

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def _get_db() -> Session:
    """Return a short-lived database session for webhook processing.

    Webhooks run outside of the normal FastAPI request lifecycle, so
    we create and close the session manually.

    Returns:
        A new ``SessionLocal`` database session.
    """
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _upgrade_user_to_paid(
    customer_id: str | None,
    subscription_id: str | None,
    db: Session,
    *,
    lookup_email: str | None = None,
) -> None:
    """Upgrade a user to the ``paid`` role and issue an API key.

    Checkout is created with ``customer_email`` (no pre-created ``customer`` on the user row),
    so the first webhook often sees a new ``cus_…`` that does not yet exist on ``User``.
    In that case we match ``lookup_email`` from Stripe-signed metadata / invoice fields,
    then persist ``stripe_customer_id`` for later subscription events.

    Args:
        customer_id:     Stripe customer ID from the event (may be new vs DB).
        subscription_id: Stripe subscription ID to persist on the user.
        db:              Active database session.
        lookup_email:    Email from Checkout ``metadata`` or invoice ``customer_email``.
    """
    user = None
    if customer_id:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user and lookup_email:
        user = db.query(User).filter(User.email == lookup_email).first()
    if not user or user.role == "paid":
        return  # No matching user or user is already paid— likely a test event; silently ignore
    if not subscription_id:
        return

    user.role = "paid"
    user.stripe_subscription_id = subscription_id
    if customer_id:
        user.stripe_customer_id = customer_id

    # Revoke any old keys before issuing the new one
    db.query(APIKey).filter(
        APIKey.user_id == user.id, APIKey.revoked.is_(False)
    ).update({"revoked": True})

    raw_key, key_hash, key_prefix = generate_api_key()
    db.add(APIKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix))
    db.commit()


def _downgrade_user_to_free(subscription_id: str, db: Session) -> None:
    """Downgrade a user to the ``free`` role and revoke their API keys.

    Args:
        subscription_id: Stripe subscription ID to identify the user.
        db:              Active database session.
    """
    user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
    if not user:
        return

    user.role = "free"
    user.stripe_subscription_id = None

    db.query(APIKey).filter(
        APIKey.user_id == user.id, APIKey.revoked.is_(False)
    ).update({"revoked": True})

    db.commit()


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default=None, alias="Stripe-Signature"),
) -> dict:
    """Receive and process Stripe webhook events.

    Stripe calls this endpoint after payment and subscription changes.
    The signature is verified before any processing occurs to prevent
    spoofed events from modifying user data.

    Args:
        request:          Raw FastAPI request (body read as bytes for signature verification).
        stripe_signature: ``Stripe-Signature`` header value sent by Stripe.

    Returns:
        ``{"received": True}`` on success.

    Raises:
        HTTPException 400: If the signature is invalid or the payload is malformed.
        HTTPException 500: If the webhook secret is not configured.
    """
    if not _WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="STRIPE_WEBHOOK_SECRET is not configured.",
        )

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=_WEBHOOK_SECRET,
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature.",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook payload.",
        )

    db = _get_db()
    try:
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            meta = session.get("metadata") or {}
            user_email = meta.get("user_email")

            _upgrade_user_to_paid(
                customer_id=session.get("customer"),
                subscription_id=session.get("subscription"),
                db=db,
                lookup_email=user_email,
            )

        elif event["type"] == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            _upgrade_user_to_paid(
                customer_id=invoice.get("customer"),
                subscription_id=invoice.get("subscription"),
                db=db,
                lookup_email=invoice.get("customer_email"),
            )

        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            _downgrade_user_to_free(
                subscription_id=subscription.get("id"),
                db=db,
            )
        elif event["type"] == "invoice.payment_failed":
            invoice = event["data"]["object"]

            _downgrade_user_to_free(
                subscription_id=invoice.get("subscription"),
                db=db,
            )

        # All other event types are acknowledged but not acted upon
    finally:
        db.close()

    return {"received": True}
