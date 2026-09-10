import urllib.parse

import pandas as pd
import streamlit as st

import auth
import db
import ui


ui.inject_base_css()
ui.require_clinic()
ui.render_sidebar_account()
ui.render_page_header("🏭 Vendor Management", "Track suppliers, contacts, and lead times, and see which products come from where.")

CLINIC_ID = auth.current_clinic_id()

vendors_df = db.get_vendors_df()
catalog_df = db.fetch_df("product_catalog", columns=["sku", "product_name", "vendor_id"])
reco_df = db.get_reorder_recommendations()
reco_lookup = reco_df.set_index("sku").to_dict("index") if not reco_df.empty else {}

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
# REORDER RECOMMENDATIONS
# ==========================================================
with st.container(border=True):
    st.markdown('<div class="tm-panel-title">Reorder Recommendations</div>', unsafe_allow_html=True)
    st.caption(
        "Suggested order quantities based on how fast each product has been used "
        "(mark items 'Used' on the Active Inventory page to build this history)."
    )

    if reco_df.empty:
        st.info("Add products to your catalog to see reorder recommendations.")
    else:
        vendor_name_lookup = dict(zip(vendors_df["id"], vendors_df["vendor_name"])) if not vendors_df.empty else {}
        display_reco = reco_df.copy()
        display_reco["Vendor"] = display_reco["vendor_id"].map(vendor_name_lookup).fillna("—")
        display_reco["Status"] = display_reco.apply(
            lambda r: "🔴 Reorder Now" if r["reorder_now"]
            else ("⚪ No Usage History Yet" if r["weekly_usage"] == 0 else "🟢 OK"),
            axis=1,
        )
        display_reco = display_reco.rename(columns={
            "product_name": "Product",
            "sku": "SKU",
            "current_stock": "Current Stock",
            "reorder_level": "Reorder Level",
            "weekly_usage": "Avg Weekly Usage",
            "suggested_week": "Suggested Qty (1 Week)",
            "suggested_month": "Suggested Qty (1 Month)",
            "suggested_year": "Suggested Qty (1 Year)",
        })[[
            "Status", "Product", "SKU", "Vendor", "Current Stock", "Reorder Level",
            "Avg Weekly Usage", "Suggested Qty (1 Week)", "Suggested Qty (1 Month)", "Suggested Qty (1 Year)",
        ]]

        st.dataframe(display_reco, use_container_width=True, height=280)

        if (reco_df["weekly_usage"] == 0).any():
            st.caption(
                "Products showing 'No Usage History Yet' don't have enough data — mark items "
                "'Used' on the Active Inventory page as you go through stock, and these numbers will fill in."
            )

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
        st.info("No products in your catalog yet — add some via Catalog Sync on the Settings page.")
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

st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# ==========================================================
# DRAFT A REORDER EMAIL
# ==========================================================
with st.container(border=True):
    st.markdown('<div class="tm-panel-title">Draft a Reorder Email</div>', unsafe_allow_html=True)

    if vendors_df.empty:
        st.info("Add a vendor above first.")
    else:
        email_vendor_options = dict(zip(vendors_df["id"], vendors_df["vendor_name"]))
        email_vendor_id = st.selectbox(
            "Vendor to email",
            options=list(email_vendor_options.keys()),
            format_func=lambda vid: email_vendor_options.get(vid, vid),
            key="email_vendor_select",
        )
        vendor_row = vendors_df.loc[vendors_df["id"] == email_vendor_id].iloc[0]

        vendor_products = catalog_df.loc[catalog_df["vendor_id"] == email_vendor_id]
        email_product_options = dict(zip(vendor_products["sku"], vendor_products["product_name"]))

        email_skus = st.multiselect(
            "Products to request",
            options=list(email_product_options.keys()),
            default=list(email_product_options.keys()),
            format_func=lambda sku: f"{email_product_options.get(sku, sku)} ({sku})",
            key="email_product_select",
        )

        clinic_name = auth.get_clinic_name() or "our clinic"
        profile = auth.get_profile()
        staff_name = (profile or {}).get("full_name") or "Clinic Staff"
        contact_first = (vendor_row.get("contact_name") or "").split(" ")[0] or "there"
        lead_time = vendor_row.get("lead_time_days")

        def format_product_line(sku):
            name = email_product_options[sku]
            info = reco_lookup.get(sku)
            if info and info["suggested_month"] > 0:
                return (
                    f"- {name} (SKU: {sku}) — suggested qty: {info['suggested_month']} "
                    f"(based on ~{info['weekly_usage']}/week usage)"
                )
            return f"- {name} (SKU: {sku})"

        product_lines = "\n".join(format_product_line(s) for s in email_skus)
        if not product_lines:
            product_lines = "- [select one or more products above]"

        lead_time_line = ""
        if pd.notna(lead_time):
            lead_time_line = f"Our standard lead time expectation is {int(lead_time)} days. "

        subject = f"Reorder Request - {clinic_name}"
        body = (
            f"Hi {contact_first},\n\n"
            f"We'd like to place a reorder with {vendor_row['vendor_name']}. "
            f"Could you please send updated pricing and availability for the following item(s)?\n\n"
            f"{product_lines}\n\n"
            f"{lead_time_line}Please let us know if any items are back-ordered.\n\n"
            f"Thank you,\n{staff_name}\n{clinic_name}"
        )

        draft_key = f"email_draft_body_{email_vendor_id}_{'_'.join(sorted(email_skus))}"
        draft_body = st.text_area(
            "Email draft (edit as needed, then send)",
            value=body,
            height=220,
            key=draft_key,
        )

        to_addr = vendor_row.get("contact_email") or ""
        mailto_url = (
            f"mailto:{urllib.parse.quote(to_addr)}"
            f"?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(draft_body)}"
        )

        send_col, note_col = st.columns([1, 3])
        with send_col:
            st.link_button("✉️ Open in Email App", mailto_url, use_container_width=True)
        with note_col:
            if not to_addr:
                st.caption("No contact email on file for this vendor — add one above to prefill the recipient.")
