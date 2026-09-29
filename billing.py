"""
Stripe subscription billing for Tagmate clinics.

Architecture note: this app has no standalone backend server to receive
Stripe webhooks (Streamlit apps only serve the app itself), so this is a
deliberately webhook-free, "pull" design for v1:

  - Starting a subscription: the app builds a Stripe Checkout Session and
    sends the admin to Stripe's own hosted payment page. Stripe redirects
    back to the app with a session_id; handle_checkout_success() fetches
    that session directly from Stripe's API and records the result.
  - Keeping status current later (renewals, a failed payment, a
    cancellation made from the Stripe portal): sync_subscription_status()
    re-fetches the subscription from Stripe's API and updates the local
    copy. It's called every time the Settings page's Billing section
    renders, so status is at most one page-load stale rather than
    depending on a webhook ever arriving.

A real webhook receiver (a tiny separate service, or a Supabase Edge
Function) would make status updates instant instead of load-triggered --
worth adding later, but not required for a first working version.

Every write to a clinic's billing columns goes through
db.get_service_client() (the Supabase service-role key), never the
regular per-session client -- see db.py and schema.sql for why: an
authenticated clinic admin must never be able to set their own
subscription_status to 'active' themselves. The only thing that can
mark a clinic active here is Stripe's own API response.
"""
from datetime import datetime, timezone

import stripe

import db
from db import with_retry


def _stripe_ready() -> None:
    stripe.api_key = db._get_setting("STRIPE_SECRET_KEY")
    if not stripe.api_key:
        raise RuntimeError(
            "Missing STRIPE_SECRET_KEY. Set it in a .env file or "
            ".streamlit/secrets.toml (see .env.example) to enable billing."
        )


def _price_id() -> str:
    price_id = db._get_setting("STRIPE_PRICE_ID")
    if not price_id:
        raise RuntimeError(
            "Missing STRIPE_PRICE_ID. Create a product/price in your Stripe "
            "Dashboard and set its price ID in .streamlit/secrets.toml or .env."
        )
    return price_id


def _app_base_url() -> str:
    url = db._get_setting("APP_BASE_URL")
    if not url:
        raise RuntimeError(
            "Missing APP_BASE_URL. Set it to this app's public URL (e.g. "
            "https://your-app.streamlit.app) in .streamlit/secrets.toml or .env "
            "so Stripe knows where to send customers back to."
        )
    return url.rstrip("/")


@with_retry
def get_billing_info(clinic_id: str) -> dict:
    """Read-only: the caller's own clinic's billing columns. Safe over the
    normal per-session client -- RLS already lets a clinic read its own
    row, this just asks for a few more columns off of it."""
    res = (
        db.get_client()
        .table("clinics")
        .select("stripe_customer_id, stripe_subscription_id, subscription_status, subscription_plan, trial_ends_at")
        .eq("id", clinic_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else {}


def _write_billing_fields(clinic_id: str, **fields) -> None:
    db.get_service_client().table("clinics").update(fields).eq("id", clinic_id).execute()


def create_checkout_session(clinic_id: str, clinic_name: str, customer_email: str) -> str:
    """Builds a Stripe Checkout Session for a new subscription (flat
    monthly price, 14-day trial) and returns the URL to send the admin
    to. Nothing is recorded locally yet -- that happens once they
    actually complete checkout and Stripe redirects back, in
    handle_checkout_success()."""
    _stripe_ready()
    base_url = _app_base_url()

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": _price_id(), "quantity": 1}],
        subscription_data={"trial_period_days": 14},
        customer_email=customer_email,
        client_reference_id=str(clinic_id),
        metadata={"clinic_id": str(clinic_id), "clinic_name": clinic_name},
        success_url=f"{base_url}/?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/?checkout=cancel",
    )
    return session.url


def handle_checkout_success(session_id: str) -> None:
    """Called once, right after Stripe redirects back with ?checkout=success
    -- looks the just-completed session up directly with Stripe (never
    trusts the URL alone) and records the customer/subscription it created.

    The clinic_id comes from the Stripe session's own client_reference_id,
    not from this browser session's login state: st.link_button opens
    Stripe's hosted checkout in a NEW tab, so the tab Stripe redirects back
    to is a brand-new, logged-out Streamlit session here -- there's no
    guarantee (and no need) for it to be logged in at all."""
    _stripe_ready()
    session = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])

    clinic_id = session.client_reference_id or (session.metadata or {}).get("clinic_id")
    if not clinic_id:
        raise RuntimeError("This Stripe checkout session has no clinic reference on it.")

    subscription = session.subscription
    fields = {"stripe_customer_id": session.customer}
    if subscription:
        fields["stripe_subscription_id"] = subscription.id
        fields["subscription_status"] = subscription.status
        if subscription.trial_end:
            fields["trial_ends_at"] = datetime.fromtimestamp(
                subscription.trial_end, tz=timezone.utc
            ).isoformat()

    _write_billing_fields(clinic_id, **fields)


def sync_subscription_status(clinic_id: str) -> dict:
    """Re-fetches the clinic's subscription from Stripe (if it has one) and
    writes the latest status locally. Returns the fresh billing_info dict.
    Cheap enough to call on every Billing section render -- one Stripe API
    call, only when a subscription actually exists."""
    info = get_billing_info(clinic_id)
    if not info.get("stripe_subscription_id"):
        return info

    _stripe_ready()
    sub = stripe.Subscription.retrieve(info["stripe_subscription_id"])

    fields = {"subscription_status": sub.status}
    if sub.trial_end:
        fields["trial_ends_at"] = datetime.fromtimestamp(sub.trial_end, tz=timezone.utc).isoformat()
    _write_billing_fields(clinic_id, **fields)

    info.update(fields)
    return info


def create_billing_portal_session(clinic_id: str) -> str:
    """Stripe's own hosted portal for an existing customer to update their
    payment method, view invoices, or cancel -- avoids building any of
    that UI ourselves."""
    info = get_billing_info(clinic_id)
    if not info.get("stripe_customer_id"):
        raise RuntimeError("This clinic doesn't have a Stripe customer yet.")

    _stripe_ready()
    portal = stripe.billing_portal.Session.create(
        customer=info["stripe_customer_id"],
        return_url=f"{_app_base_url()}/",
    )
    return portal.url
