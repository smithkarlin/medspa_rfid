import streamlit as st

import auth
import db
import ui

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(
    page_title="tagmate | RFID Medspa Inventory",
    page_icon="🏷️",
    layout="wide"
)

ui.inject_base_css()

if not auth.is_logged_in():
    ui.render_page_header("🏷️ tagmate", "RFID & Barcode Inventory for Medspas")

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
    ui.render_page_header("🏷️ Welcome to tagmate", "One more step — let's set up your clinic.")
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
# LOGGED IN, CLINIC SET UP: WELCOME / HOME SCREEN
# ==========================================================
ui.render_sidebar_account()

clinic_name = auth.get_clinic_name()
ui.render_page_header(
    "🏷️ Welcome to tagmate",
    f"You're signed in to **{clinic_name}**. Use the sidebar to get started."
)

df_inv = db.get_all_tagged_inventory_df()
kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    ui.render_kpi_card("Items In Stock", f"{len(df_inv):,}")
with kpi2:
    ui.render_kpi_card("Storage Locations", f"{len(db.get_locations_list()):,}")
with kpi3:
    ui.render_kpi_card("Product SKUs", f"{len(db.get_catalog_options()):,}")

st.markdown("---")
st.markdown(
    """
#### Getting Around
- **📥 Express Intake** — scan a box barcode, then an RFID tag, to commission new stock.
- **📋 Daily Count** — walk a room with a handheld scanner to reconcile inventory.
- **📦 Active Inventory** — see everything currently tagged and in stock.
- **⚙️ Settings** — manage storage locations and sync your product catalog.
- **📊 Analytics** — dashboards on stock levels, usage, and expiration risk.
- **🏭 Vendors** — manage suppliers and see which products come from where.
"""
)
