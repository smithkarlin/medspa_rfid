import streamlit as st

import auth
import db
import ui


ui.inject_base_css()
ui.require_clinic()
ui.render_sidebar_account()

ui.render_page_header("📦 Active Inventory", "Live view of all commissioned RFID-tagged stock.")

# ==========================================================
# ACTIVE INVENTORY VIEW
# ==========================================================
st.subheader("📊 Live Commissioned Stock")

df_inv = db.get_all_tagged_inventory_df()

if df_inv.empty:
    st.info("No items tagged yet. Use the 'Express Intake' page to commission your first RFID asset.")
else:
    in_stock_count = int((df_inv["Status"] == "In Stock").sum())
    used_count = int((df_inv["Status"] == "Used").sum())

    m1, m2, m3 = st.columns(3)
    m1.metric("In Stock", in_stock_count)
    m2.metric("Used", used_count)
    m3.metric("Total Tagged", len(df_inv))

    status_filter = st.selectbox("Show", options=["In Stock", "Used", "All"], index=0)
    if status_filter == "All":
        display_df = df_inv
    else:
        display_df = df_inv[df_inv["Status"] == status_filter]

    st.dataframe(display_df, use_container_width=True)

    st.markdown("---")

    # ==========================================================
    # MARK AN ITEM AS USED
    # ==========================================================
    st.markdown('<div class="tm-panel-title">Mark an Item as Used</div>', unsafe_allow_html=True)
    st.caption(
        "When a product is applied or consumed, mark its RFID tag as used. "
        "This is what powers the reorder recommendations on the Vendors page."
    )

    in_stock_df = df_inv[df_inv["Status"] == "In Stock"]
    if in_stock_df.empty:
        st.info("Nothing currently in stock to mark as used.")
    else:
        epc_options = {
            row["RFID Tag (EPC)"]: f"{row['Product Name']} — {row['RFID Tag (EPC)']} ({row['Storage Location']})"
            for _, row in in_stock_df.iterrows()
        }
        use_col, btn_col = st.columns([3, 1])
        with use_col:
            epc_to_use = st.selectbox(
                "Select item",
                options=list(epc_options.keys()),
                format_func=lambda epc: epc_options.get(epc, epc),
                label_visibility="collapsed",
            )
        with btn_col:
            if st.button("✅ Mark as Used", use_container_width=True):
                db.mark_item_used(epc_to_use)
                st.success("Marked as used.")
                st.rerun()
