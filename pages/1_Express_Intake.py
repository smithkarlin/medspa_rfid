import re
from datetime import datetime
import streamlit as st

import auth
import db
import ui


ui.inject_base_css()
ui.require_clinic()
ui.render_top_bar()

CLINIC_ID = auth.current_clinic_id()


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


ui.render_page_header("📥 Express Intake", "Scan box barcode to auto-fill product details, then scan RFID tag to complete binding.")

# ==========================================================
# GS1 BARCODE TO RFID COMMISSIONING
# ==========================================================
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
