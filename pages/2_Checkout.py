import streamlit as st

import auth
import db
import ui


ui.inject_base_css()
ui.require_clinic()
ui.render_top_bar()

ui.render_page_header("Checkout", "Scan an RFID tag to mark a product used and remove it from active stock.")

if "pending_checkout" not in st.session_state:
    st.session_state["pending_checkout"] = None
if "checkout_result" not in st.session_state:
    st.session_state["checkout_result"] = None


def process_checkout_scan():
    """Looks the tag up and, if it's a valid in-stock item, queues it for
    the user to confirm below rather than checking it out immediately --
    a scan alone (no separate button click) shouldn't be enough on its
    own to remove something from stock. A not-found or already-used tag
    is just reported; there's nothing to confirm in either case."""
    raw = st.session_state.get("checkout_scan_input", "").strip()
    if not raw:
        return

    epc = raw.upper()
    # Clear the field immediately, same as Express Intake's scan fields,
    # so a repeated trigger pull never concatenates onto old text.
    st.session_state["checkout_scan_input"] = ""

    row = db.get_tagged_item(epc)

    if row is None:
        st.session_state["checkout_result"] = {"epc": epc, "found": False}
        st.session_state["pending_checkout"] = None
    elif row["status"] == "Used":
        st.session_state["checkout_result"] = {"epc": epc, "found": True, "already_used": True, "row": row}
        st.session_state["pending_checkout"] = None
    else:
        st.session_state["checkout_result"] = None
        st.session_state["pending_checkout"] = {"epc": epc, "row": row}


# ==========================================================
# SCAN TO CHECK OUT
# ==========================================================
st.subheader("Scan to Check Out")
st.caption("Place the cursor below and scan the RFID tag on the product you just used.")

st.text_input(
    "Scan RFID Tag (UHF EPC Hex Code)",
    key="checkout_scan_input",
    placeholder="Wave RFID reader over tag (e.g. E200470D...)...",
    on_change=process_checkout_scan,
)

# ==========================================================
# CONFIRMATION -- shared by both the scan flow above and Manual
# Checkout below. Nothing is actually checked out (no mark_item_used
# call) until the user explicitly confirms here.
# ==========================================================
pending = st.session_state.get("pending_checkout")
if pending:
    p_row = pending["row"]
    st.warning(
        f"🟡 **Confirm Check-Out:** `{pending['epc']}` — **{p_row['product_name']}** "
        f"(Lot: `{p_row['lot_number']}`) at **{p_row['location']}**. "
        "This will remove it from active stock."
    )
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("✅ Confirm Check-Out", type="primary", use_container_width=True, key="confirm_checkout_btn"):
            db.mark_item_used(pending["epc"])
            st.session_state["checkout_result"] = {
                "epc": pending["epc"], "found": True, "already_used": False, "row": p_row,
            }
            st.session_state["pending_checkout"] = None
            st.rerun()
    with cancel_col:
        if st.button("✖️ Cancel", use_container_width=True, key="cancel_checkout_btn"):
            st.session_state["pending_checkout"] = None
            st.rerun()

result = st.session_state.get("checkout_result")
if result:
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
st.subheader("Manual Checkout")
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
        if st.button("Check Out", use_container_width=True):
            # Queues the same confirmation panel above rather than
            # checking out immediately -- picking from the list and
            # clicking still gets a final "are you sure" before it's
            # actually processed.
            st.session_state["pending_checkout"] = {"epc": epc_to_use, "row": db.get_tagged_item(epc_to_use)}
            st.session_state["checkout_result"] = None
            st.rerun()

st.markdown("---")

# ==========================================================
# RECENTLY CHECKED OUT
# ==========================================================
st.subheader("Recently Checked Out")

used_df = df_inv[df_inv["Status"] == "Used"] if not df_inv.empty else df_inv
if used_df.empty:
    st.info("No items checked out yet.")
else:
    recent = used_df.sort_values(by="Used At", ascending=False, na_position="last").head(10)
    st.dataframe(
        recent[["RFID Tag (EPC)", "Product Name", "Lot Number", "Storage Location", "Used At"]],
        use_container_width=True,
    )
