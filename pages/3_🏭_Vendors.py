import pandas as pd
import streamlit as st

import auth
import db
import ui

st.set_page_config(page_title="tagmate Vendors", page_icon="🏭", layout="wide")

if not auth.is_logged_in() or not auth.has_clinic():
    st.warning("Please log in from the main tagmate page first.")
    st.stop()

ui.inject_base_css()
ui.render_page_header("🏭 Vendor Management", "Track suppliers, contacts, and lead times, and see which products come from where.")

CLINIC_ID = auth.current_clinic_id()

vendors_df = db.get_vendors_df()
catalog_df = db.fetch_df("product_catalog", columns=["sku", "product_name", "vendor_id"])

# ==========================================================
# KPI ROW
# ==========================================================
kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    ui.render_kpi_card("Total Vendors", f"{len(vendors_df):,}")

with kpi2:
    if not vendors_df.empty and vendors_df["lead_time_days"].notna().any():
        avg_lead = vendors_df["lead_time_days"].dropna().astype(float).mean()
        lead_display = f"{avg_lead:.0f} days"
    else:
        lead_display = "—"
    ui.render_kpi_card("Avg Lead Time", lead_display)

with kpi3:
    total_products = len(catalog_df)
    linked_products = int(catalog_df["vendor_id"].notna().sum()) if total_products else 0
    ui.render_kpi_card("Products Linked", f"{linked_products:,} / {total_products:,}")

st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# ==========================================================
# ADD VENDOR + VENDOR LIST
# ==========================================================
add_col, list_col = st.columns([1, 2], gap="large")

with add_col:
    with st.container(border=True):
        st.markdown('<div class="tm-panel-title">Add Vendor</div>', unsafe_allow_html=True)
        with st.form("add_vendor_form", clear_on_submit=True):
            v_name = st.text_input("Vendor Name")
            v_contact = st.text_input("Contact Name")
            v_email = st.text_input("Contact Email")
            v_phone = st.text_input("Contact Phone")
            v_lead = st.number_input("Lead Time (days)", min_value=0, step=1, value=0)
            v_notes = st.text_area("Notes", height=80)
            submitted = st.form_submit_button("➕ Add Vendor", type="primary", use_container_width=True)
            if submitted:
                if v_name.strip():
                    try:
                        db.add_vendor(
                            v_name.strip(), CLINIC_ID,
                            contact_name=v_contact.strip(),
                            contact_email=v_email.strip(),
                            contact_phone=v_phone.strip(),
                            lead_time_days=int(v_lead) if v_lead else None,
                            notes=v_notes.strip(),
                        )
                        st.success(f"Added **{v_name.strip()}**")
                        st.rerun()
                    except db.DuplicateError:
                        st.error("A vendor with that name already exists.")
                else:
                    st.error("Vendor name is required.")

with list_col:
    with st.container(border=True):
        st.markdown('<div class="tm-panel-title">Your Vendors</div>', unsafe_allow_html=True)
        if vendors_df.empty:
            st.info("No vendors yet — add your first supplier on the left.")
        else:
            display_df = vendors_df.rename(columns={
                "vendor_name": "Vendor",
                "contact_name": "Contact",
                "contact_email": "Email",
                "contact_phone": "Phone",
                "lead_time_days": "Lead Time (days)",
                "notes": "Notes",
            })[["Vendor", "Contact", "Email", "Phone", "Lead Time (days)", "Notes"]]
            st.dataframe(display_df, use_container_width=True, height=300)

            del_col1, del_col2 = st.columns([3, 1])
            with del_col1:
                vendor_to_delete = st.selectbox(
                    "Remove a vendor", options=["None"] + list(vendors_df["vendor_name"]), label_visibility="collapsed"
                )
            with del_col2:
                if st.button("🗑️ Delete Vendor", use_container_width=True):
                    if vendor_to_delete != "None":
                        vid = vendors_df.loc[vendors_df["vendor_name"] == vendor_to_delete, "id"].iloc[0]
                        db.delete_vendor(vid)
                        st.success(f"Removed {vendor_to_delete}")
                        st.rerun()

st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# ==========================================================
# ASSIGN PRODUCTS TO A VENDOR
# ==========================================================
with st.container(border=True):
    st.markdown('<div class="tm-panel-title">Assign Products to a Vendor</div>', unsafe_allow_html=True)

    if vendors_df.empty:
        st.info("Add a vendor above first.")
    elif catalog_df.empty:
        st.info("No products in your catalog yet — add some via Catalog Sync on the main tagmate page.")
    else:
        vendor_options = dict(zip(vendors_df["id"], vendors_df["vendor_name"]))
        selected_vendor_id = st.selectbox(
            "Vendor",
            options=list(vendor_options.keys()),
            format_func=lambda vid: vendor_options.get(vid, vid),
        )

        product_options = dict(zip(catalog_df["sku"], catalog_df["product_name"]))
        already_assigned = catalog_df.loc[catalog_df["vendor_id"] == selected_vendor_id, "sku"].tolist()

        selected_skus = st.multiselect(
            "Products supplied by this vendor",
            options=list(product_options.keys()),
            default=already_assigned,
            format_func=lambda sku: f"{product_options.get(sku, sku)} ({sku})",
        )

        if st.button("💾 Save Assignment", type="primary"):
            to_unassign = [s for s in already_assigned if s not in selected_skus]
            db.unassign_vendor_from_skus(to_unassign)
            db.assign_vendor_to_skus(selected_vendor_id, selected_skus)
            st.success("Vendor assignment updated.")
            st.rerun()
