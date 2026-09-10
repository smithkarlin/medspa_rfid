import streamlit as st

import auth
import db
import ui


ui.inject_base_css()
ui.require_clinic()
ui.render_top_bar()

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
    st.caption("Ready to use an item? Head to the **Checkout** page to scan it out.")
