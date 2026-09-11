"""
Shared design system for the Tagmate app: colors, fonts, and reusable CSS
components (page headers, KPI cards, status badges, the top account bar)
used across interface.py and every page in pages/, so the app reads as
one consistent, professional platform instead of separately-styled
screens.

The dark sidebar / light workspace split itself is set globally in
.streamlit/config.toml (Streamlit's own theme engine); this module adds
the finer-grained pieces Streamlit's theme config doesn't cover -- KPI
cards, section titles, status pills, the sidebar's active-page pill, and
the top-right account bar.
"""
import base64

import streamlit as st

INK = "#1B2340"
MUTED = "#7C879E"
BORDER = "#E7EAF3"
BG = "#F6F8FC"
CARD = "#FFFFFF"

BLUE_1 = "#5B9BF7"
BLUE_2 = "#3B6FE0"
LIGHT_BLUE = "#BEE3FF"
GREEN = "#2FAE6E"
AMBER = "#E8A33D"
RED_EXPIRING = "#F0664E"

BASE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

.tm-page-title {{
    font-family: 'Baloo 2', sans-serif;
    font-weight: 700;
    font-size: 2rem;
    color: {INK};
    margin: 0;
}}
.tm-page-caption {{
    color: {BLUE_2};
    font-weight: 500;
    font-size: 0.95rem;
    margin-top: 0.15rem;
    margin-bottom: 1.5rem;
}}
.tm-panel-title {{
    font-family: 'Baloo 2', sans-serif;
    font-weight: 600;
    font-size: 1.1rem;
    color: {INK};
    margin: 0 0 0.6rem 0;
}}

/* ---- Brand wordmark, echoing the logo's two-tone treatment ---- */
.tm-brand {{
    display: flex;
    align-items: baseline;
    gap: 0.3rem;
    padding-top: 0.35rem;
    line-height: 1;
}}
.tm-brand-main {{
    font-family: 'Baloo 2', sans-serif;
    font-weight: 700;
    font-size: 1.4rem;
    color: {INK};
}}
.tm-brand-sub {{
    font-family: 'Baloo 2', sans-serif;
    font-weight: 600;
    font-size: 1.15rem;
    color: {BLUE_2};
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
    font-family: 'Baloo 2', sans-serif;
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

/* ---- Sidebar brand block: icon + wordmark + clinic-name subtitle ---- */
.tm-sidebar-brand {{
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.9rem 1rem 1.1rem 1rem;
    margin-bottom: 0.25rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}}
.tm-sidebar-brand img {{
    width: 40px;
    height: 40px;
    border-radius: 9px;
    object-fit: cover;
    flex-shrink: 0;
}}
.tm-sidebar-brand-text {{
    display: flex;
    flex-direction: column;
    line-height: 1.2;
    min-width: 0;
}}
.tm-sidebar-brand-name {{
    font-family: 'Baloo 2', sans-serif;
    font-weight: 700;
    font-size: 1.15rem;
    color: #FFFFFF;
}}
.tm-sidebar-brand-sub {{
    font-size: 0.75rem;
    color: #9AA3B8;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

/* ---- Sidebar nav: every item bold, active item highlighted light blue ---- */
[data-testid="stSidebarNav"] {{ padding-top: 0.5rem; }}
[data-testid="stSidebarNav"] ul {{ padding-top: 0.25rem; }}
[data-testid="stSidebarNav"] a {{
    border-radius: 10px;
    margin: 2px 0.9rem;
    padding: 0.55rem 0.9rem;
    transition: background 0.15s ease;
}}
[data-testid="stSidebarNav"] a span {{
    font-weight: 700 !important;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: rgba(255,255,255,0.07);
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {LIGHT_BLUE};
}}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{
    color: {INK} !important;
    font-weight: 700 !important;
}}

/* ---- Top account bar icon buttons (rendered inside a keyed container) ---- */
.st-key-tm_topbar_icons button {{
    border-radius: 999px !important;
    min-width: 2.4rem;
    padding: 0.35rem 0.6rem !important;
}}
</style>
"""


def inject_base_css() -> None:
    st.markdown(BASE_CSS, unsafe_allow_html=True)


@st.cache_data
def _icon_data_uri() -> str:
    """Base64-encode the Tagmate icon once per process so the sidebar
    brand block can embed it directly as an <img> without relying on
    Streamlit's static file server."""
    with open("assets/tagmate_icon.png", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{encoded}"


def render_sidebar_brand(clinic_name: str = "") -> None:
    """Custom sidebar header rendered above the auto-generated page nav:
    the Tagmate icon, the 'Tagmate' wordmark, and a subtitle (the signed
    -in clinic's name once known, else 'Analytics'). Replaces st.logo()
    so the icon, wordmark, and subtitle can share one styled block."""
    subtitle = clinic_name.strip() if clinic_name and clinic_name.strip() else "Analytics"
    with st.sidebar:
        st.markdown(
            f'<div class="tm-sidebar-brand">'
            f'<img src="{_icon_data_uri()}" alt="Tagmate" />'
            f'<div class="tm-sidebar-brand-text">'
            f'<span class="tm-sidebar-brand-name">Tagmate</span>'
            f'<span class="tm-sidebar-brand-sub">{subtitle}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )


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


def render_top_bar() -> None:
    """Top-of-page account bar: brand wordmark on the left, and on the
    right a clinic switcher, notifications, a settings shortcut, help,
    and an account menu (signed-in email, staff name, Log Out) -- all as
    popovers so no extra page navigation is needed to see them."""
    import auth

    left, right = st.columns([3, 4])

    with left:
        st.markdown(
            '<div class="tm-brand"><span class="tm-brand-main">Tagmate</span>'
            '<span class="tm-brand-sub">Analytics</span></div>',
            unsafe_allow_html=True,
        )

    with right:
        clinic_col, icons_col = st.columns([2, 3])

        with clinic_col:
            clinic_name = auth.get_clinic_name() or "Clinic"
            with st.popover(f"{clinic_name}  ▾", use_container_width=True):
                st.caption("Clinic")
                st.write(f"**{clinic_name}**")
                st.page_link("pages/5_Settings.py", label="Manage Settings", icon=":material/settings:")

        with icons_col:
            with st.container(key="tm_topbar_icons"):
                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    with st.popover("🔔"):
                        st.caption("Notifications")
                        st.write("No new notifications yet.")
                with b2:
                    with st.popover("⚙️"):
                        st.caption("Settings")
                        st.page_link("pages/5_Settings.py", label="Open Settings", icon=":material/settings:")
                with b3:
                    with st.popover("❓"):
                        st.caption("Help")
                        st.write(
                            "Set up locations and sync your catalog on the **Settings** page. "
                            "Commission stock on **Express Intake**, and scan items out on **Checkout**."
                        )
                with b4:
                    user = auth.get_user()
                    profile = auth.get_profile()
                    initial = (user.email[0].upper() if user and user.email else "?")
                    with st.popover(initial):
                        if user:
                            st.caption("Signed in as")
                            st.write(f"**{user.email}**")
                        if profile and profile.get("full_name"):
                            st.caption(f"Staff: {profile['full_name']}")
                        st.button("Log Out", on_click=auth.sign_out, use_container_width=True, key="topbar_logout")

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
