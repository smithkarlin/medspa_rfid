"""
Supabase Auth + clinic (tenant) onboarding for the tagmate app.

Each browser session gets its own Supabase client (stored in
st.session_state, not st.cache_resource) so that one visitor logging in
never leaks their session into another visitor's browser tab on the same
running server -- important once this app has more than one clinic's
staff using it at once.
"""
import streamlit as st

import db


def get_user():
    return st.session_state.get("sb_user")


def get_profile():
    return st.session_state.get("sb_profile")


def is_logged_in() -> bool:
    return get_user() is not None


def has_clinic() -> bool:
    return get_profile() is not None


def sign_up(email: str, password: str):
    client = db.get_client()
    return client.auth.sign_up({"email": email, "password": password})


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


def _load_profile():
    user = get_user()
    if not user:
        return None
    client = db.get_client()
    res = client.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    return res.data[0] if res.data else None


def refresh_profile():
    st.session_state["sb_profile"] = _load_profile()


def create_clinic(clinic_name: str, full_name: str) -> None:
    """Run once, right after a brand-new user's first login, to create
    their clinic and an admin profile tied to it."""
    client = db.get_client()
    user = get_user()
    clinic_res = client.table("clinics").insert({"name": clinic_name}).execute()
    clinic_id = clinic_res.data[0]["id"]
    client.table("profiles").insert({
        "id": user.id,
        "clinic_id": clinic_id,
        "full_name": full_name,
        "role": "admin",
    }).execute()
    refresh_profile()


def current_clinic_id():
    profile = get_profile()
    return profile["clinic_id"] if profile else None
