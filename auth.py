"""
Supabase Auth + clinic (tenant) onboarding for the Tagmate app.

Each browser session gets its own Supabase client (stored in
st.session_state, not st.cache_resource) so that one visitor logging in
never leaks their session into another visitor's browser tab on the same
running server -- important once this app has more than one clinic's
staff using it at once.
"""
import streamlit as st

import db
from db import with_retry


def get_user():
    return st.session_state.get("sb_user")


def get_profile():
    return st.session_state.get("sb_profile")


def is_logged_in() -> bool:
    return get_user() is not None


def has_clinic() -> bool:
    return get_profile() is not None


def is_admin() -> bool:
    profile = get_profile()
    return bool(profile) and profile.get("role") == "admin"


@with_retry
def sign_up(email: str, password: str, metadata: dict | None = None):
    """metadata (e.g. {"terms_accepted_at": "<iso timestamp>"}) is stored
    on the Supabase auth user as user_metadata -- a lightweight audit
    trail that this email accepted the Terms of Service / Privacy Policy
    at signup, without needing a schema change."""
    client = db.get_client()
    payload = {"email": email, "password": password}
    if metadata:
        payload["options"] = {"data": metadata}
    return client.auth.sign_up(payload)


@with_retry
def sign_in(email: str, password: str):
    client = db.get_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    # Belt-and-suspenders: make sure table() calls on this session's client
    # carry the signed-in user's JWT, so Postgres Row Level Security can see
    # auth.uid() and actually enforce clinic isolation.
    client.postgrest.auth(result.session.access_token)
    st.session_state["sb_user"] = result.user
    st.session_state["sb_profile"] = _load_profile()
    return result


def sign_out():
    client = db.get_client()
    try:
        client.auth.sign_out()
    except Exception:
        pass
    for key in ("sb_user", "sb_profile", "_sb_client"):
        st.session_state.pop(key, None)


@with_retry
def _load_profile():
    user = get_user()
    if not user:
        return None
    client = db.get_client()
    res = client.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    return res.data[0] if res.data else None


def refresh_profile():
    st.session_state["sb_profile"] = _load_profile()


@with_retry
def create_clinic(clinic_name: str, full_name: str) -> None:
    """Run once, right after a brand-new user's first login, to create
    their clinic and an admin profile tied to it.

    Goes through the create_clinic_and_profile SQL function (SECURITY
    DEFINER) rather than inserting directly: at this moment the user has
    no profile row yet, so RLS's own SELECT policy on clinics would
    otherwise make the freshly-inserted row invisible (INSERT ... RETURNING
    is itself subject to the SELECT policy) even though the insert itself
    succeeded -- see schema.sql for the full explanation.
    """
    client = db.get_client()
    client.rpc("create_clinic_and_profile", {"clinic_name": clinic_name, "full_name": full_name}).execute()
    refresh_profile()


def current_clinic_id():
    profile = get_profile()
    return profile["clinic_id"] if profile else None


@with_retry
def get_pending_invite():
    """Looks up a pending invite matching the signed-in user's own auth
    email -- used on the clinic-setup gate to offer 'join your team'
    instead of 'create a new clinic' when someone was invited. Safe to
    call before a profile row exists (that's the whole point)."""
    client = db.get_client()
    res = client.rpc("get_my_pending_invite", {}).execute()
    return res.data[0] if res.data else None


@with_retry
def accept_invite(full_name: str) -> None:
    """Joins the signed-in user to the clinic that invited them, using
    whichever pending invite matches their auth email. No-ops safely if
    there isn't one -- has_clinic() just stays False and the normal
    'create a clinic' form takes over."""
    client = db.get_client()
    client.rpc("accept_pending_invite", {"full_name": full_name}).execute()
    refresh_profile()


@with_retry
def get_clinic_name():
    clinic_id = current_clinic_id()
    if not clinic_id:
        return None
    client = db.get_client()
    res = client.table("clinics").select("name").eq("id", clinic_id).limit(1).execute()
    return res.data[0]["name"] if res.data else None
