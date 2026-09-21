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


ui.render_page_header("Express Intake", "Optionally scan a box barcode to auto-fill product details, then scan RFID tag to complete binding.")

# ==========================================================
# GS1 BARCODE TO RFID COMMISSIONING
# ==========================================================
st.subheader("Express GS1 Barcode ➔ RFID Commissioning")
st.caption("Scanning a barcode is optional -- it auto-fills the product, expiration, and lot below, but you can skip it and fill those in yourself.")

if "widget_sku" not in st.session_state:
    st.session_state["widget_sku"] = "CUSTOM"
if "widget_exp" not in st.session_state:
    st.session_state["widget_exp"] = datetime.today().date()
if "widget_lot" not in st.session_state:
    st.session_state["widget_lot"] = ""
if "last_scanned_barcode" not in st.session_state:
    st.session_state["last_scanned_barcode"] = ""
if "last_scanned_rfid" not in st.session_state:
    st.session_state["last_scanned_rfid"] = ""
if "confirmed_rfid_epc" not in st.session_state:
    st.session_state["confirmed_rfid_epc"] = ""
if "rfid_duplicate_warning" not in st.session_state:
    st.session_state["rfid_duplicate_warning"] = None

catalog_options = db.get_catalog_options()
catalog_options["CUSTOM"] = "Custom / Unlisted Product"

def process_scanned_barcode():
    scanned_val = st.session_state.intake_barcode_input.strip()
    if not scanned_val:
        return

    if scanned_val != st.session_state.last_scanned_barcode:
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
    # else: identical to the last scan already read -- a scanner trigger
    # pressed repeatedly on the same barcode is held/ignored here instead
    # of being reprocessed (re-matched, re-toasted) every time.

    # Always clear the raw field right after reading it, whether this scan
    # matched a product or was a repeat -- so the box is empty and ready
    # for the next trigger pull instead of letting new keystrokes pile up
    # after old, already-read text.
    st.session_state.intake_barcode_input = ""


def process_scanned_rfid():
    """Same debounce-and-clear approach as process_scanned_barcode() above,
    plus a live duplicate-tag check: an EPC already bound to another item
    is rejected immediately (with who/where it's already assigned to)
    instead of only failing once the whole form is submitted."""
    epc_val = st.session_state.intake_rfid_input.strip()
    if not epc_val:
        return

    if epc_val != st.session_state.last_scanned_rfid:
        st.session_state.last_scanned_rfid = epc_val
        existing = db.get_tagged_item(epc_val)
        if existing:
            st.session_state.confirmed_rfid_epc = ""
            st.session_state.rfid_duplicate_warning = (
                f"This RFID tag is already assigned to **{existing['product_name']}** "
                f"at **{existing['location']}** (status: {existing['status']}). "
                "Scan a different tag -- the same tag can't be bound to two items."
            )
        else:
            st.session_state.confirmed_rfid_epc = epc_val
            st.session_state.rfid_duplicate_warning = None
            st.toast(f"✅ RFID Captured: {epc_val}")
    # else: identical to the last tag already read -- repeated trigger
    # pulls on the same tag are held/ignored instead of re-checked.

    # Always clear the raw field right after reading it -- see
    # process_scanned_barcode() for why. The actual EPC to commission is
    # kept in confirmed_rfid_epc, not in this widget's own value.
    st.session_state.intake_rfid_input = ""

raw_barcode = st.text_input(
    "1. Scan Box GS1 DataMatrix or UPC Barcode (Optional)",
    key="intake_barcode_input",
    placeholder="Scan barcode here (e.g. 01003002345678901726123110LOT998822)... or leave blank and select the product below.",
    on_change=process_scanned_barcode,
    help="Optional. Supports GS1 2D DataMatrix (Botox, Dysport, Juvederm) and standard UPC codes. "
         "Skip this and pick the product manually below if you don't have a barcode to scan."
)

if st.session_state.last_scanned_barcode:
    st.success(
        f"🟢 **Scan Captured!** Raw Barcode: `{st.session_state.last_scanned_barcode}` "
        f"| Selected SKU: `{st.session_state.widget_sku}` "
        f"| LOT: `{st.session_state.widget_lot}` "
        f"| EXP: `{st.session_state.widget_exp}`"
    )

st.markdown("---")

col_sku, col_name, col_exp, col_lot = st.columns(4)
sku_options = list(catalog_options.keys())

with col_sku:
    selected_sku = st.selectbox(
        "Product / SKU",
        options=sku_options,
        format_func=lambda x: catalog_options.get(x, x),
        key="widget_sku"
    )

with col_name:
    # Recomputed and written into session_state on every run, before this
    # keyed widget renders, rather than passed as value= -- a keyless (or
    # key'd-but-value=) text_input only applies value= the first time it's
    # ever rendered and then ignores further changes to it, which is why
    # this was silently staying blank after a barcode match instead of
    # tracking the selected SKU.
    st.session_state["widget_product_name"] = (
        catalog_options.get(selected_sku, "") if selected_sku != "CUSTOM" else ""
    )
    st.text_input(
        "Product Name",
        key="widget_product_name",
        disabled=True,
        help="Auto-filled from the matched barcode, or from the SKU you pick above.",
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
    st.text_input(
        "2. Scan Physical RFID Tag (UHF EPC Hex Code)",
        key="intake_rfid_input",
        placeholder="Wave RFID reader over tag (e.g. E200470D...)...",
        on_change=process_scanned_rfid,
        help="Place cursor here and scan the physical RFID tag attached to the box/bottle. "
             "Scanning the same tag again while it's already captured won't re-read it, and "
             "a tag already bound to another item is flagged right away."
    )

with col_loc:
    current_locations = db.get_locations_list()
    target_location = st.selectbox(
        "3. Assign to Storage Location",
        options=current_locations if current_locations else ["Main Vault / Refrigerator"],
        key="intake_location_select"
    )

if st.session_state.rfid_duplicate_warning:
    st.error(f"🚫 **Tag Already In Use:** {st.session_state.rfid_duplicate_warning}")

st.markdown("---")

if st.button("🔗 Complete Tag Commissioning & Save to Stock", type="primary", use_container_width=True):
    clean_epc = st.session_state.confirmed_rfid_epc
    if not clean_epc:
        st.error("❌ Missing RFID EPC! Please scan a physical RFID tag to complete binding.")
    elif st.session_state.rfid_duplicate_warning:
        st.error("❌ That RFID tag is already assigned to another item. Scan a different tag before commissioning.")
    elif selected_sku == "CUSTOM":
        st.error("❌ Please select or upload a valid product SKU before commissioning.")
    else:
        prod_name = catalog_options.get(selected_sku, "Unknown Product")

        try:
            db.insert_tagged_item(
                clean_epc, selected_sku, prod_name,
                expiration_date, lot_number.strip(), target_location, CLINIC_ID
            )

            st.balloons()
            st.toast(f"✅ Commissioned {prod_name} to {target_location}!")
            st.success(f"🎉 **Successfully Commissioned!** Tag `{clean_epc}` bound to **{prod_name}** (Lot: `{lot_number.strip()}`, Exp: `{expiration_date}`). Saved to **{target_location}**.")

            # Reset the whole form for the next item -- both the derived
            # product fields and the raw scan state for barcode and RFID,
            # so neither field is left showing the just-commissioned item.
            st.session_state["widget_sku"] = "CUSTOM"
            st.session_state["widget_exp"] = datetime.today().date()
            st.session_state["widget_lot"] = ""
            st.session_state["intake_barcode_input"] = ""
            st.session_state["last_scanned_barcode"] = ""
            st.session_state["intake_rfid_input"] = ""
            st.session_state["last_scanned_rfid"] = ""
            st.session_state["confirmed_rfid_epc"] = ""
            st.session_state["rfid_duplicate_warning"] = None
            st.rerun()

        except db.DuplicateError:
            st.error(f"❌ **Duplicate Tag Error:** RFID Tag `{clean_epc}` is already assigned to another item in your clinic!")
