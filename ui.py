"""
Shared design system for the Tagmate app: colors, fonts, and reusable CSS
components (page headers, KPI cards, status badges) used across
interface.py and every page in pages/, so the app reads as one
consistent, professional platform instead of separately-styled screens.

The dark sidebar / light workspace split itself is set globally in
.streamlit/config.toml (Streamlit's own theme engine); this module adds
the finer-grained pieces Streamlit's theme config doesn't cover -- KPI
cards, section titles, status pills.
"""
import streamlit as st

INK = "#1B2340"
MUTED = "#7C879E"
BORDER = "#E7EAF3"
BG = "#F6F8FC"
CARD = "#FFFFFF"

BLUE_1 = "#5B9BF7"
BLUE_2 = "#3B6FE0"
GREEN = "#2FAE6E"
AMBER = "#E8A33D"
RED_EXPIRING = "#F0664E"

BASE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

.tm-page-title {{
    font-family: 'Poppins', sans-serif;
    font-weight: 600;
    font-size: 2rem;
    color: {INK};
    margin: 0;
}}
.tm-page-caption {{
    color: {MUTED};
    font-size: 0.95rem;
    margin-top: 0.15rem;
    margin-bottom: 1.5rem;
}}
.tm-panel-title {{
    font-family: 'Poppins', sans-serif;
    font-weight: 600;
    font-size: 1.1rem;
    color: {INK};
    margin: 0 0 0.6rem 0;
}}

/* ---- Gradient KPI cards, shared across Analytics / Vendors / Inventory ---- */
.tm-kpi-card {{
    position: relative;
    overflow: hidden;
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    background: linear-gradient(135deg, {BLUE_1} 0%, {BLUE_2} 100%);
    box-shadow: 0 8px 20px rgba(59,111,224,0.20);
    min-height: 100px;
    margin-bottom: 0.5rem;
}}
.tm-kpi-label {{
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.85);
    margin-bottom: 0.4rem;
}}
.tm-kpi-value {{
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    font-size: 1.7rem;
    color: #FFFFFF;
    line-height: 1.1;
}}

/* ---- Status pills ---- */
.tm-badge {{
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
}}
.tm-badge-success {{ background: #E3F7EC; color: {GREEN}; }}
.tm-badge-warning {{ background: #FDF1DE; color: {AMBER}; }}
.tm-badge-danger  {{ background: #FCE7E4; color: {RED_EXPIRING}; }}
.tm-badge-info    {{ background: #E9F1FE; color: {BLUE_2}; }}
.tm-badge-neutral {{ background: {BORDER}; color: {MUTED}; }}

/* ---- Table / input polish ---- */
.stDataFrame {{ border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden; }}
div[data-baseweb="select"] > div {{ border-radius: 10px !important; border-color: {BORDER} !important; }}
div[data-testid="stForm"] {{ border: 1px solid {BORDER}; border-radius: 12px; padding: 1rem 1.2rem; }}

/* Sidebar: a little breathing room above the nav links */
[data-testid="stSidebarNav"] ul {{ padding-top: 0.25rem; }}
</style>
"""


def inject_base_css() -> None:
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def render_page_header(title: str, caption: str = "") -> None:
    caption_html = f'<div class="tm-page-caption">{caption}</div>' if caption else ""
    st.markdown(f'<h1 class="tm-page-title">{title}</h1>{caption_html}', unsafe_allow_html=True)


def render_kpi_card(label: str, value: str) -> None:
    st.markdown(
        f'<div class="tm-kpi-card"><div class="tm-kpi-label">{label}</div>'
        f'<div class="tm-kpi-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "neutral") -> str:
    """HTML for a colored status pill. kind: success, warning, danger, info, neutral."""
    return f'<span class="tm-badge tm-badge-{kind}">{text}</span>'


def require_clinic() -> None:
    """Auth gate for every page under pages/. Stops the page (with a
    friendly message) unless the user is logged in AND has finished
    clinic setup. Import auth lazily to avoid a circular import at
    module load time."""
    import auth
    if not auth.is_logged_in() or not auth.has_clinic():
        st.warning("Please log in from the **Tagmate** home page first.")
        st.stop()


def render_sidebar_account() -> None:
    """Signed-in-as / clinic / staff / log-out block, shown in the
    sidebar on every page."""
    import auth
    with st.sidebar:
        profile = auth.get_profile()
        clinic_name = auth.get_clinic_name()
        st.caption(f"Signed in as **{auth.get_user().email}**")
        if clinic_name:
            st.caption(f"Clinic: **{clinic_name}**")
        if profile and profile.get("full_name"):
            st.caption(f"Staff: {profile['full_name']}")
        st.button("Log Out", on_click=auth.sign_out, use_container_width=True)
