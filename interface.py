import re
from datetime import datetime
import pandas as pd
import streamlit as st

import auth
import db
import ui

# ==========================================================
# CALLBACK FUNCTIONS & PARSERS
# ==========================================================
def parse_gs1_barcode(raw_barcode: str):
    data = {"gtin": None, "expiration": None, "lot": None}
    if not raw_barcode:
        return data

    clean_code = raw_barcode.strip().replace("(", "").replace(")", "").replace("\x1d", "")
    clean_code = re.sub(r'^\][a-zA-Z0-9]{2}', '', clean_code)

    gtin_match = re.search(r'01(\d{14})', clean_code)
    if gtin_match:
        data["gtin"] = gtin_match.group(1)

    exp_match = re.search(r'17(\d{6})', clean_code)
    if exp_match:
        raw_date = exp_match.group(1)
        try:
            parsed_date = datetime.strptime(raw_date, "%y%m%d").date()
            data["expiration"] = parsed_date
        except ValueError:
            data["expiration"] = None

    lot_match = re.search(r'10([A-Za-z0-9\-_]{2,20})', clean_code)
    if lot_match:
        data["lot"] = lot_match.group(1)

    return data


def process_rfid_scan():
    """Callback for continuous RFID room scanning in Tab 2."""
    raw_input = st.session_state.get("audit_rfid_stream", "").strip()
    if not raw_input:
        return

    extracted_tokens = re.findall(r'E2[0-9A-Fa-f]{22}', raw_input)
    cleaned_tokens = [t.strip().upper() for t in extracted_tokens]

    existing_set = set(st.session_state.get("scanned_buffer", []))
    new_unique_tags = []

    for tag in cleaned_tokens:
        if tag not in existing_set and tag not in new_unique_tags:
            new_unique_tags.append(tag)

    if new_unique_tags:
        if "scanned_buffer" not in st.session_state:
            st.session_state.scanned_buffer = []
        st.session_state.scanned_buffer.extend(new_unique_tags)
        st.toast(f"✅ Added {len(new_unique_tags)} new distinct tag(s)!")
    else:
        st.toast("⚠️ Ignored duplicate tag(s) from scan.")

    st.session_state["audit_rfid_stream"] = ""

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
    ui.render_page_header("🏷️ Welcome to tagmate", "One more step \u2014 let's set up your clinic.")
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

CLINIC_ID = auth.current_clinic_id()

with st.sidebar:
    profile = auth.get_profile()
    clinic_name = auth.get_clinic_name()
    st.caption(f"Signed in as **{auth.get_user().email}**")
    if clinic_name:
        st.caption(f"Clinic: **{clinic_name}**")
    if profile and profile.get("full_name"):
        st.caption(f"Staff: {profile['full_name']}")
    st.button("Log Out", on_click=auth.sign_out, use_container_width=True)

ui.render_page_header("🏷️ tagmate inventory controller", "UHF RFID & Barcode Intake System | Pilot Build")

tab_intake, tab_count, tab_inventory, tab_admin = st.tabs([
    "📥 Express Intake",
    "📋 Daily Inventory Count",
    "📊 Active Inventory",
    "⚙️ Catalog & Location Settings"
])

# ==========================================================
# TAB 1: GS1 BARCODE TO RFID COMMISSIONING
# ==========================================================
with tab_intake:
    st.subheader("⚡ Express GS1 Barcode ➔ RFID Commissioning")
    st.caption("Scan box barcode to auto-fill product details, then scan RFID tag to complete binding.")

    if "widget_sku" not in st.session_state:
        st.session_state["widget_sku"] = "CUSTOM"
    if "widget_exp" not in st.session_state:
        st.session_state["widget_exp"] = datetime.today().date()
    if "widget_lot" not in st.session_state:
        st.session_state["widget_lot"] = ""
    if "last_scanned_barcode" not in st.session_state:
        st.session_state["last_scanned_barcode"] = ""

    catalog_options = db.get_catalog_options()
    catalog_options["CUSTOM"] = "Custom / Unlisted Product"

    def process_scanned_barcode():
        scanned_val = st.session_state.intake_barcode_input.strip()
        if scanned_val and scanned_val != st.session_state.last_scanned_barcode:
            st.session_state.last_scanned_barcode = scanned_val
            parsed = parse_gs1_barcode(scanned_val)

            if parsed["expiration"]:
                st.session_state["widget_exp"] = parsed["expiration"]

            if parsed["lot"]:
                st.session_state["widget_lot"] = parsed["lot"]

            search_key = parsed["gtin"] if parsed["gtin"] else scanned_val
            matched = db.lookup_barcode_in_catalog(search_key)
            if matched and matched[0] in catalog_options:
                st.session_state["widget_sku"] = matched[0]
                st.toast(f"✅ Auto-Matched Catalog: {matched[1]}")

    raw_barcode = st.text_input(
        "1. Scan Box GS1 DataMatrix or UPC Barcode",
        key="intake_barcode_input",
        placeholder="Scan barcode here (e.g. 01003002345678901726123110LOT998822)...",
        on_change=process_scanned_barcode,
        help="Supports GS1 2D DataMatrix (Botox, Dysport, Juvederm) and standard UPC codes."
    )

    if st.session_state.last_scanned_barcode:
        st.success(
            f"🟢 **Scan Captured!** Raw Barcode: `{st.session_state.last_scanned_barcode}` "
            f"| Selected SKU: `{st.session_state.widget_sku}` "
            f"| LOT: `{st.session_state.widget_lot}` "
            f"| EXP: `{st.session_state.widget_exp}`"
        )

    st.markdown("---")

    col_sku, col_exp, col_lot = st.columns(3)
    sku_options = list(catalog_options.keys())

    with col_sku:
        selected_sku = st.selectbox(
            "Product / SKU",
            options=sku_options,
            format_func=lambda x: catalog_options.get(x, x),
            key="widget_sku"
        )

    with col_exp:
        expiration_date = st.date_input(
            "Expiration Date",
            key="widget_exp"
        )

    with col_lot:
        lot_number = st.text_input(
            "Lot Number",
            key="widget_lot"
        )

    st.markdown("---")

    col_rfid, col_loc = st.columns(2)

    with col_rfid:
        rfid_epc = st.text_input(
            "2. Scan Physical RFID Tag (UHF EPC Hex Code)",
            key="intake_rfid_input",
            placeholder="Wave RFID reader over tag (e.g. E200470D...)...",
            help="Place cursor here and scan the physical RFID tag attached to the box/bottle."
        )

    with col_loc:
        current_locations = db.get_locations_list()
        target_location = st.selectbox(
            "3. Assign to Storage Location",
            options=current_locations if current_locations else ["Main Vault / Refrigerator"],
            key="intake_location_select"
        )

    st.markdown("---")

    if st.button("🔗 Complete Tag Commissioning & Save to Stock", type="primary", use_container_width=True):
        if not rfid_epc.strip():
            st.error("❌ Missing RFID EPC! Please scan a physical RFID tag to complete binding.")
        elif selected_sku == "CUSTOM":
            st.error("❌ Please select or upload a valid product SKU before commissioning.")
        else:
            prod_name = catalog_options.get(selected_sku, "Unknown Product")
            clean_epc = rfid_epc.strip()

            try:
                db.insert_tagged_item(
                    clean_epc, selected_sku, prod_name,
                    expiration_date, lot_number.strip(), target_location, CLINIC_ID
                )

                st.balloons()
                st.toast(f"✅ Commissioned {prod_name} to {target_location}!")
                st.success(f"🎉 **Successfully Commissioned!** Tag `{clean_epc}` bound to **{prod_name}** (Lot: `{lot_number.strip()}`, Exp: `{expiration_date}`). Saved to **{target_location}**.")

                st.session_state["widget_sku"] = "CUSTOM"
                st.session_state["widget_exp"] = datetime.today().date()
                st.session_state["widget_lot"] = ""
                st.session_state["last_scanned_barcode"] = ""
                st.rerun()

            except db.DuplicateError:
                st.error(f"❌ **Duplicate Tag Error:** RFID Tag `{clean_epc}` is already assigned to another item in the database!")

# ==========================================================
# TAB 2: DAILY INVENTORY COUNT (CONTINUOUS ROOM SCAN)
# ==========================================================
with tab_count:
    st.subheader("📋 Continuous Room Inventory Audit")
    st.caption("Select a room, click 'Start Room Scan', walk around scanning tags with your handheld reader, and click 'Stop & Process Scan' to reconcile.")

    current_locations = db.get_locations_list()
    audit_location = st.selectbox(
        "📍 Select Target Room / Location to Audit:",
        options=current_locations if current_locations else ["Main Vault / Refrigerator"],
        key="audit_room_select"
    )

    if "is_scanning" not in st.session_state:
        st.session_state.is_scanning = False
    if "scanned_buffer" not in st.session_state:
        st.session_state.scanned_buffer = []

    expected_count = db.get_expected_count(audit_location)

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Expected Items in Room", expected_count)
    unique_buffered_count = len(set(st.session_state.scanned_buffer))
    col_m2.metric("Buffered Unique Tags Scanned", unique_buffered_count)

    diff_prelim = unique_buffered_count - expected_count
    col_m3.metric("Live Variance", diff_prelim, delta_color="inverse")

    st.markdown("---")

    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])

    with col_btn1:
        if st.button("▶️ Start Room Scan", disabled=st.session_state.is_scanning, use_container_width=True, type="primary"):
            st.session_state.is_scanning = True
            st.session_state.scanned_buffer = []
            if "last_audit_summary" in st.session_state:
                del st.session_state.last_audit_summary
            st.rerun()

    with col_btn2:
        if st.button("⏹️ Stop & Process Scan", disabled=not st.session_state.is_scanning, use_container_width=True):
            st.session_state.is_scanning = False

            unique_epcs = list(set(st.session_state.scanned_buffer))
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            processed_results = []

            shifted_count = 0
            verified_count = 0
            unregistered_count = 0

            for epc in unique_epcs:
                row = db.get_tagged_item(epc)

                if row:
                    product_name = row["product_name"]
                    old_location = row["location"]
                    lot_number = row["lot_number"]

                    if old_location and old_location != audit_location:
                        scan_status = f"🟨 Room Shifted (Moved from '{old_location}')"
                        shifted_count += 1
                    else:
                        scan_status = "🟢 Verified in Room"
                        verified_count += 1

                    db.update_tagged_location(epc, audit_location, now_str)
                else:
                    product_name = "Unregistered EPC Tag"
                    scan_status = "🟦 New/Unregistered Tag"
                    old_location = "N/A"
                    lot_number = "N/A"
                    unregistered_count += 1

                processed_results.append({
                    "EPC / Tag": epc,
                    "Product Name": product_name,
                    "Lot Number": lot_number,
                    "Previous Location": old_location,
                    "Updated Location": audit_location,
                    "Audit Status": scan_status
                })

            discrepancy = len(unique_epcs) - expected_count
            db.insert_daily_audit(audit_location, expected_count, len(unique_epcs), discrepancy, "Clinic Staff", CLINIC_ID)

            st.session_state.last_audit_summary = {
                "results": processed_results,
                "room": audit_location,
                "total_scanned": len(unique_epcs),
                "expected": expected_count,
                "shifted": shifted_count,
                "verified": verified_count,
                "unregistered": unregistered_count
            }
            st.rerun()

    with col_btn3:
        if st.button("🗑️ Reset", use_container_width=True):
            st.session_state.is_scanning = False
            st.session_state.scanned_buffer = []
            if "last_audit_summary" in st.session_state:
                del st.session_state.last_audit_summary
            st.rerun()

    if st.session_state.is_scanning:
        st.info(f"📡 **SCANNING ACTIVE in {audit_location}...** Walk around the room with your handheld scanner. Focus input field below.")

        st.text_input(
            "Handheld RFID Reader Stream Input:",
            key="audit_rfid_stream",
            placeholder="Hold trigger / scan stream here...",
            on_change=process_rfid_scan
        )

    if "last_audit_summary" in st.session_state:
        summary = st.session_state.last_audit_summary
        st.markdown("---")
        st.markdown(f"### 📊 Audit Results Summary for **{summary['room']}**")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Scanned", summary['total_scanned'])
        c2.metric("Verified in Room", summary['verified'])
        c3.metric("Room Shifted Items", summary['shifted'])
        c4.metric("Unregistered Tags", summary['unregistered'])

        df_summary = pd.DataFrame(summary['results'])

        def highlight_entire_row(row):
            status = str(row["Audit Status"])
            if "Room Shifted" in status:
                return ["background-color: #FFF3CD; color: #856404; font-weight: bold;"] * len(row)
            elif "Verified" in status:
                return ["background-color: #D4EDDA; color: #155724;"] * len(row)
            elif "New" in status:
                return ["background-color: #CCE5FF; color: #004085;"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_summary.style.apply(highlight_entire_row, axis=1),
            use_container_width=True,
            height=380
        )

# ==========================================================
# TAB 3: ACTIVE INVENTORY VIEW
# ==========================================================
with tab_inventory:
    st.subheader("📊 Live Commissioned Stock")

    df_inv = db.get_all_tagged_inventory_df()

    if df_inv.empty:
        st.info("No items tagged yet. Use the 'Express Intake' tab to commission your first RFID asset.")
    else:
        st.dataframe(df_inv, use_container_width=True)
        st.metric("Total Items In Stock", len(df_inv))

# ==========================================================
# TAB 4: ADMIN & CATALOG MANAGEMENT
# ==========================================================
with tab_admin:
    st.subheader("📍 Storage Location Manager")

    col_add_loc, col_del_loc = st.columns(2)

    with col_add_loc:
        st.markdown("#### Add New Location")
        new_loc_name = st.text_input("New Location Name", placeholder="e.g. Fridge 3 - Med Room")
        if st.button("➕ Add Location"):
            if new_loc_name.strip():
                try:
                    db.add_location(new_loc_name.strip(), CLINIC_ID)
                    st.success(f"Added **{new_loc_name.strip()}**!")
                    st.rerun()
                except db.DuplicateError:
                    st.error("Location already exists.")

    with col_del_loc:
        st.markdown("#### Remove Location")
        existing_locs = db.get_locations_list()
        loc_to_delete = st.selectbox("Select Location to Remove", options=existing_locs if existing_locs else ["None"])
        if st.button("🗑️ Delete Location"):
            if loc_to_delete and loc_to_delete != "None":
                db.delete_location(loc_to_delete)
                st.success(f"Removed **{loc_to_delete}**!")
                st.rerun()

    st.markdown("---")

    st.subheader("📤 MDware Catalog Sync")
    uploaded_file = st.file_uploader("Upload MDware Inventory CSV", type=["csv"])

    if uploaded_file is not None:
        try:
            df_raw = pd.read_csv(uploaded_file, dtype=str)

            col_map = {}
            for col in df_raw.columns:
                c_lower = col.strip().lower()
                if "sku" in c_lower or "item code" in c_lower:
                    col_map["sku"] = col
                elif "barcode" in c_lower or "upc" in c_lower or "gtin" in c_lower:
                    col_map["barcode"] = col
                elif "product name" in c_lower or "description" in c_lower:
                    col_map["product_name"] = col
                elif "cost" in c_lower or "price" in c_lower:
                    col_map["unit_cost"] = col
                elif "reorder" in c_lower or "min" in c_lower:
                    col_map["reorder_level"] = col

            df_clean = pd.DataFrame()
            df_clean["sku"] = df_raw[col_map.get("sku", df_raw.columns[0])].str.strip()
            df_clean["barcode"] = df_raw[col_map.get("barcode", df_raw.columns[1])].str.strip()
            df_clean["product_name"] = df_raw[col_map.get("product_name", df_raw.columns[2])].str.strip()

            if "unit_cost" in col_map:
                cost_clean = df_raw[col_map["unit_cost"]].astype(str).str.replace("$", "").str.replace(",", "")
                df_clean["unit_cost"] = pd.to_numeric(cost_clean, errors="coerce").fillna(0.0)
            else:
                df_clean["unit_cost"] = 0.0

            if "reorder_level" in col_map:
                df_clean["reorder_level"] = pd.to_numeric(df_raw[col_map["reorder_level"]], errors="coerce").fillna(5).astype(int)
            else:
                df_clean["reorder_level"] = 5

            df_clean = df_clean.dropna(subset=["sku", "product_name"])

            st.success(f"✓ Parsed **{len(df_clean)} product records**.")

            if st.button("🚀 Sync to Master Database Catalog", type="primary"):
                db.sync_catalog(df_clean, CLINIC_ID)

                st.balloons()
                st.success("✅ Master Catalog updated!")
                st.rerun()

        except Exception as e:
            st.error(f"Error processing CSV: {e}")
