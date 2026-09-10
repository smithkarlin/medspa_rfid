import pandas as pd
import streamlit as st

import auth
import db
import ui


ui.inject_base_css()
ui.require_clinic()
ui.render_sidebar_account()

CLINIC_ID = auth.current_clinic_id()

ui.render_page_header("⚙️ Catalog & Location Settings", "Manage storage locations and sync your product catalog.")

with st.expander("🧪 Load Sample Data (preview the dashboards)"):
    st.caption(
        "Adds 3 sample products (Botox, Juvederm, Vitamin C Serum) with demo "
        "RFID tags, barcode stock, and a sample vendor, so Analytics and "
        "Vendors have something to show right away."
    )
    if st.button("Load Sample Data"):
        db.load_sample_data(CLINIC_ID)
        st.balloons()
        st.success("Sample data loaded! Check the Analytics and Vendors pages.")
        st.rerun()

st.markdown("---")

# ==========================================================
# STORAGE LOCATION MANAGER
# ==========================================================
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

MDWARE_TEMPLATE_CSV = (
    "SKU,Barcode/UPC,Product Name,Unit Cost,Reorder Level\n"
    "BTX-100,00300090856100,Botox 100U,395.00,5\n"
    "JUV-UXC,00300090862200,Juvederm Ultra XC,275.00,10\n"
)

dl_col, up_col = st.columns([1, 2])
with dl_col:
    st.download_button(
        "⬇ Download Catalog Template (CSV)",
        data=MDWARE_TEMPLATE_CSV,
        file_name="mdware_catalog_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption("Fill this in with your own products, then upload it below.")

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
