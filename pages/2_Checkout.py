import streamlit as st

import auth
import db
import ui


ui.inject_base_css()
ui.require_clinic()
ui.render_sidebar_account()

ui.render_page_header("✅ Checkout", "Scan an RFID tag to mark a product used and remove it from active stock.")


def process_checkout_scan():
    raw = st.session_state.get("checkout_scan_input", "").strip()
    if not raw:
        return

    epc = raw.upper()
    row = db.get_tagged_item(epc)

    if row is None:
        st.session_state["checkout_result"] = {"epc": epc, "found": False}
    elif row["status"] == "Used":
        st.session_state["checkout_result"] = {"epc": epc, "found": True, "already_used": True, "row": row}
    else:
        db.mark_item_used(epc)
        st.session_state["checkout_result"] = {"epc": epc, "found": True, "already_used": False, "row": row}

    st.session_state["checkout_scan_input"] = ""


# ==========================================================
# SCAN TO CHECK OUT
# ==========================================================
st.subheader("📡 Scan to Check Out")
st.caption("Place the cursor below and scan the RFID tag on the product you just used.")

st.text_input(
    "Scan RFID Tag (UHF EPC Hex Code)",
    key="checkout_scan_input",
    placeholder="Wave RFID reader over tag (e.g. E200470D...)...",
    on_change=process_checkout_scan,
)

if "checkout_result" in st.session_state:
    result = st.session_state["checkout_result"]
    if not result["found"]:
        st.error(f"❌ No item found for tag `{result['epc']}`. Check the scan or commission it first via Express Intake.")
    elif result["already_used"]:
        st.warning(f"⚠️ Tag `{result['epc']}` ({result['row']['product_name']}) was already checked out / used.")
    else:
        row = result["row"]
        st.success(
            f"✅ **Checked Out!** `{result['epc']}` — **{row['product_name']}** "
            f"(Lot: `{row['lot_number']}`) removed from active stock at **{row['location']}**."
        )

st.markdown("---")

# ==========================================================
# MANUAL CHECKOUT (no scanner handy)
# ==========================================================
st.subheader("🖊️ Manual Checkout")
st.caption("No scanner on hand? Pick the item from your current in-stock list instead.")

df_inv = db.get_all_tagged_inventory_df()
in_stock_df = df_inv[df_inv["Status"] == "In Stock"] if not df_inv.empty else df_inv

if in_stock_df.empty:
    st.info("Nothing currently in stock to check out.")
else:
    epc_options = {
        row["RFID Tag (EPC)"]: f"{row['Product Name']} — {row['RFID Tag (EPC)']} ({row['Storage Location']})"
        for _, row in in_stock_df.iterrows()
    }
    manual_col, btn_col = st.columns([3, 1])
    with manual_col:
        epc_to_use = st.selectbox(
            "Select item",
            options=list(epc_options.keys()),
            format_func=lambda epc: epc_options.get(epc, epc),
            label_visibility="collapsed",
        )
    with btn_col:
        if st.button("✅ Check Out", use_container_width=True):
            db.mark_item_used(epc_to_use)
            st.success(f"Checked out `{epc_to_use}`.")
            st.rerun()

st.markdown("---")

# ==========================================================
# RECENTLY CHECKED OUT
# ==========================================================
st.subheader("🕒 Recently Checked Out")

used_df = df_inv[df_inv["Status"] == "Used"] if not df_inv.empty else df_inv
if used_df.empty:
    st.info("No items checked out yet.")
else:
    recent = used_df.sort_values(by="Used At", ascending=False, na_position="last").head(10)
    st.dataframe(
        recent[["RFID Tag (EPC)", "Product Name", "Lot Number", "Storage Location", "Used At"]],
        use_container_width=True,
    )
