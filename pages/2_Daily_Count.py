from datetime import datetime
import pandas as pd
import streamlit as st

import auth
import db
import ui

st.set_page_config(
    page_title="tagmate | Daily Inventory Count",
    page_icon="📋",
    layout="wide"
)

ui.inject_base_css()
ui.require_clinic()
ui.render_sidebar_account()

CLINIC_ID = auth.current_clinic_id()


def process_rfid_scan():
    """Callback for continuous RFID room scanning."""
    raw_input = st.session_state.get("audit_rfid_stream", "").strip()
    if not raw_input:
        return

    import re
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


ui.render_page_header("📋 Daily Inventory Count", "Continuous room inventory audit via handheld RFID scanning.")

# ==========================================================
# DAILY INVENTORY COUNT (CONTINUOUS ROOM SCAN)
# ==========================================================
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
