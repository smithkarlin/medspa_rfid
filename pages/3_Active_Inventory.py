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
    st.dataframe(df_inv, use_container_width=True)
    st.metric("Total Items In Stock", len(df_inv))
