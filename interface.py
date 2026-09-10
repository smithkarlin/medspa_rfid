import streamlit as st

import auth
import db
import ui

# ==========================================================
# PAGE CONFIG (called once, here, for the whole app)
# ==========================================================
st.set_page_config(
    page_title="Tagmate | RFID Medspa Inventory",
    page_icon="🏷️",
    layout="wide"
)

st.logo("assets/tagmate_icon.png", size="large")
ui.inject_base_css()

if not auth.is_logged_in():
    ui.render_page_header("Tagmate", "RFID & Barcode Inventory for Medspas")

    login_tab, signup_tab = st.tabs(["Log In", "Sign Up"])

    with login_tab:
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Log In", type="primary", use_container_width=True):
                try:
                    auth.sign_in(login_email.strip(), login_password)
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with signup_tab:
        with st.form("signup_form"):
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input("Password", type="password", key="signup_password")
            if st.form_submit_button("Create Account", type="primary", use_container_width=True):
                try:
                    result = auth.sign_up(signup_email.strip(), signup_password)
                    if result.session:
                        auth.sign_in(signup_email.strip(), signup_password)
                        st.rerun()
                    else:
                        st.success("Account created! Check your email to confirm it, then log in.")
                except Exception as e:
                    st.error(f"Sign up failed: {e}")

    st.stop()

if not auth.has_clinic():
    ui.render_page_header("Welcome to Tagmate", "One more step — let's set up your clinic.")
    with st.form("clinic_setup_form"):
        clinic_name = st.text_input("Medspa / Clinic Name")
        full_name = st.text_input("Your Name")
        if st.form_submit_button("Create Clinic", type="primary", use_container_width=True):
            if clinic_name.strip():
                auth.create_clinic(clinic_name.strip(), full_name.strip())
                st.rerun()
            else:
                st.error("Please enter a clinic name.")
    st.stop()

# ==========================================================
# NAVIGATION
# Every page runs through this file first (Streamlit re-executes the
# entrypoint on every navigation), so the login/clinic gates above apply
# to the whole app -- no page is reachable without passing them.
# ==========================================================
# (path, title, description) for every page besides Main -- kept as plain
# tuples (not read back off the st.Page objects) so the sidebar labels and
# the "Getting Around" links on the home page always show the exact same
# text, regardless of what attributes a given Streamlit version exposes on
# a StreamlitPage object.
PAGE_SPECS = [
    ("intake", "pages/1_Express_Intake.py", "Express Intake", ":material/qr_code_scanner:",
     "Scan a box barcode, then an RFID tag, to commission new stock."),
    ("checkout", "pages/2_Checkout.py", "Checkout", ":material/task_alt:",
     "Scan an RFID tag to mark a product used and remove it from active stock."),
    ("count", "pages/3_Daily_Count.py", "Daily Count", ":material/fact_check:",
     "Walk a room with a handheld scanner to reconcile inventory."),
    ("inventory", "pages/4_Active_Inventory.py", "Active Inventory", ":material/inventory_2:",
     "See everything currently tagged and in stock."),
    ("settings", "pages/5_Settings.py", "Settings", ":material/settings:",
     "Manage storage locations and sync your product catalog."),
    ("analytics", "pages/6_Analytics.py", "Analytics", ":material/insights:",
     "Dashboards on stock levels, usage, and expiration risk."),
    ("vendors", "pages/7_Vendors.py", "Vendors", ":material/local_shipping:",
     "Manage suppliers and see which products come from where."),
]

pages = {key: st.Page(path, title=title, icon=icon) for key, path, title, icon, _ in PAGE_SPECS}


def render_home():
    ui.render_top_bar()

    clinic_name = auth.get_clinic_name()
    ui.render_page_header(
        "Welcome to Tagmate",
        f"You're signed in to **{clinic_name}**. Use the menu to get started."
    )

    df_inv = db.get_all_tagged_inventory_df()
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        ui.render_kpi_card("Items In Stock", f"{len(df_inv):,}")
    with kpi2:
        ui.render_kpi_card("Storage Locations", f"{len(db.get_locations_list()):,}")
    with kpi3:
        ui.render_kpi_card("Product SKUs", f"{len(db.get_catalog_options()):,}")

    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="tm-panel-title">Getting Around</div>', unsafe_allow_html=True)

        link_col1, link_col2 = st.columns(2)
        columns = [link_col1, link_col2]
        for i, (key, _path, title, _icon, description) in enumerate(PAGE_SPECS):
            with columns[i % 2]:
                st.page_link(pages[key], label=title, use_container_width=True)
                st.caption(description)


nav_pages = [st.Page(render_home, title="Main", icon=":material/dashboard:", default=True)] + list(pages.values())
pg = st.navigation(nav_pages)
pg.run()
