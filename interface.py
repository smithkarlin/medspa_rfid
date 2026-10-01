from datetime import datetime, timezone

import streamlit as st

import auth
import billing
import db
import ui


def _legal_doc_text(filename: str) -> str:
    try:
        with open(filename, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"_{filename} not found._"

# ==========================================================
# PAGE CONFIG (called once, here, for the whole app)
# ==========================================================
st.set_page_config(
    page_title="Tagmate | RFID Medspa Inventory",
    page_icon="🏷️",
    layout="wide"
)

ui.inject_base_css()

# ==========================================================
# STRIPE CHECKOUT RETURN
# Handled here, before the login gate -- st.link_button opens Stripe's
# hosted checkout in a NEW browser tab, so the tab Stripe redirects back
# to is a brand-new Streamlit session with no login state of its own,
# regardless of whether the original tab (where "Subscribe" was clicked)
# is still signed in. billing.handle_checkout_success() gets the clinic
# to credit from the Stripe session itself (client_reference_id), not
# from this session's auth state, so this works either way. See
# billing.py's module docstring for why this app is webhook-free (pull,
# not push) for v1.
# ==========================================================
checkout_flag = st.query_params.get("checkout")
if checkout_flag == "success":
    session_id = st.query_params.get("session_id")
    if session_id:
        try:
            billing.handle_checkout_success(session_id)
            st.toast("✅ Subscription activated! You can close this tab.")
        except Exception as e:
            st.error(f"Couldn't confirm your subscription with Stripe: {e}")
    st.query_params.clear()
elif checkout_flag == "cancel":
    st.toast("Checkout canceled -- no charge was made.")
    st.query_params.clear()

if not auth.is_logged_in():
    ui.render_sidebar_brand()
    ui.render_page_header("Tagmate", "RFID & Barcode Inventory for Medspas")

    login_tab, signup_tab = st.tabs(["Log In", "Sign Up"])

    with login_tab:
        if st.session_state.get("show_password_reset"):
            st.subheader("Reset Your Password")

            with st.form("request_reset_form"):
                st.caption("Step 1: Enter your email to get a reset code.")
                reset_email = st.text_input(
                    "Email",
                    key="reset_request_email",
                    value=st.session_state.get("reset_email_sent_to", ""),
                )
                if st.form_submit_button("Send Reset Code", use_container_width=True):
                    try:
                        auth.send_password_reset(reset_email.strip())
                        st.session_state["reset_email_sent_to"] = reset_email.strip()
                        st.success("If that email has an account, a reset code is on its way -- check your inbox.")
                    except Exception as e:
                        st.error(f"Couldn't send reset email: {e}")

            with st.form("complete_reset_form"):
                st.caption("Step 2: Enter the code from that email and your new password.")
                complete_email = st.text_input(
                    "Email",
                    key="reset_complete_email",
                    value=st.session_state.get("reset_email_sent_to", ""),
                )
                reset_code = st.text_input("Reset Code (from the email)", key="reset_code")
                new_password = st.text_input("New Password", type="password", key="reset_new_password")
                confirm_password = st.text_input("Confirm New Password", type="password", key="reset_confirm_password")
                if st.form_submit_button("Reset Password", type="primary", use_container_width=True):
                    if not reset_code.strip():
                        st.error("Enter the reset code from your email.")
                    elif new_password != confirm_password:
                        st.error("Passwords don't match.")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        try:
                            auth.reset_password_with_code(complete_email.strip(), reset_code.strip(), new_password)
                            st.success("Password updated! Click \"Back to Log In\" and sign in with your new password.")
                            st.session_state.pop("reset_email_sent_to", None)
                        except Exception as e:
                            st.error(f"Couldn't reset password: {e}")

            if st.button("← Back to Log In"):
                st.session_state["show_password_reset"] = False
                st.rerun()

        else:
            with st.form("login_form"):
                login_email = st.text_input("Email", key="login_email")
                login_password = st.text_input("Password", type="password", key="login_password")
                if st.form_submit_button("Log In", type="primary", use_container_width=True):
                    try:
                        auth.sign_in(login_email.strip(), login_password)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Login failed: {e}")

            if st.button("Forgot your password?"):
                st.session_state["show_password_reset"] = True
                st.rerun()

    with signup_tab:
        with st.form("signup_form"):
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input("Password", type="password", key="signup_password")

            with st.expander("Read the Terms of Service"):
                st.markdown(_legal_doc_text("TERMS_OF_SERVICE.md"))
            with st.expander("Read the Privacy Policy"):
                st.markdown(_legal_doc_text("PRIVACY_POLICY.md"))

            agreed_to_terms = st.checkbox("I agree to the Terms of Service and Privacy Policy")

            if st.form_submit_button("Create Account", type="primary", use_container_width=True):
                if not agreed_to_terms:
                    st.error("Please agree to the Terms of Service and Privacy Policy to continue.")
                else:
                    try:
                        terms_accepted_at = datetime.now(timezone.utc).isoformat()
                        result = auth.sign_up(
                            signup_email.strip(), signup_password,
                            metadata={"terms_accepted_at": terms_accepted_at},
                        )
                        if result.session:
                            auth.sign_in(signup_email.strip(), signup_password)
                            st.rerun()
                        else:
                            st.success("Account created! Check your email to confirm it, then log in.")
                    except Exception as e:
                        st.error(f"Sign up failed: {e}")

    st.stop()

if not auth.has_clinic():
    pending_invite = auth.get_pending_invite()

    if pending_invite:
        ui.render_sidebar_brand(pending_invite["clinic_name"])
        ui.render_page_header(
            "You're Invited!",
            f"Join **{pending_invite['clinic_name']}** on Tagmate as {pending_invite['role']}."
        )
        with st.form("accept_invite_form"):
            invite_full_name = st.text_input("Your Name")
            if st.form_submit_button("Join Clinic", type="primary", use_container_width=True):
                auth.accept_invite(invite_full_name.strip())
                st.rerun()
        st.stop()

    ui.render_sidebar_brand()
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

ui.render_sidebar_brand(auth.get_clinic_name())


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
