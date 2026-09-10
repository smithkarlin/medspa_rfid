import urllib.parse
import uuid

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
    st.caption("See the full reorder recommendations table on the **Analytics** page.")

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

        if not email_product_options:
            st.info("This vendor has no products assigned yet — assign some above first.")
        else:
            # Reset the order builder whenever the vendor changes, since the
            # product dropdown options are vendor-specific.
            if st.session_state.get("reorder_email_vendor") != email_vendor_id:
                st.session_state["reorder_email_vendor"] = email_vendor_id
                st.session_state["reorder_email_lines"] = [uuid.uuid4().hex[:8]]
            if "reorder_email_lines" not in st.session_state:
                st.session_state["reorder_email_lines"] = [uuid.uuid4().hex[:8]]

            st.markdown("**Order Line Items**")
            h1, h2, h3, h4, h5 = st.columns([3, 2.3, 1.3, 1.5, 0.6])
            h1.caption("Product")
            h2.caption("Quantity")
            h3.caption("Custom Qty")
            h4.caption("Line Cost")

            order_rows = []
            BASIS_LABELS = ["1 Week", "1 Month", "1 Year", "Manual"]

            for line_id in list(st.session_state["reorder_email_lines"]):
                c1, c2, c3, c4, c5 = st.columns([3, 2.3, 1.3, 1.5, 0.6])

                with c1:
                    sku_choice = st.selectbox(
                        "Product",
                        options=[None] + list(email_product_options.keys()),
                        format_func=lambda s: "Select a product…" if s is None else f"{email_product_options.get(s, s)} ({s})",
                        key=f"reorder_line_sku_{line_id}",
                        label_visibility="collapsed",
                    )

                info = reco_lookup.get(sku_choice, {}) if sku_choice else {}
                qty_by_basis = {
                    "1 Week": info.get("suggested_week", 0),
                    "1 Month": info.get("suggested_month", 0),
                    "1 Year": info.get("suggested_year", 0),
                }
                unit_cost = info.get("unit_cost", 0.0) or 0.0

                with c2:
                    basis_choice = st.selectbox(
                        "Quantity",
                        options=[f"{b} (~{qty_by_basis[b]})" if b != "Manual" else b for b in BASIS_LABELS],
                        key=f"reorder_line_basis_{line_id}",
                        label_visibility="collapsed",
                        disabled=(sku_choice is None),
                    )
                basis_label = basis_choice.split(" (")[0]

                with c3:
                    if basis_label == "Manual":
                        qty = st.number_input(
                            "Qty", min_value=0, step=1, value=0,
                            key=f"reorder_line_manual_{line_id}",
                            label_visibility="collapsed",
                            disabled=(sku_choice is None),
                        )
                    else:
                        qty = qty_by_basis.get(basis_label, 0)
                        st.markdown(f"<div style='padding-top:0.5rem;'>{qty}</div>", unsafe_allow_html=True)

                line_cost = (qty * unit_cost) if sku_choice else 0.0

                with c4:
                    st.markdown(f"<div style='padding-top:0.5rem;'>${line_cost:,.2f}</div>", unsafe_allow_html=True)

                with c5:
                    remove_clicked = st.button("✕", key=f"reorder_line_remove_{line_id}")
                    if remove_clicked and len(st.session_state["reorder_email_lines"]) > 1:
                        st.session_state["reorder_email_lines"].remove(line_id)
                        st.rerun()

                if sku_choice and qty > 0:
                    order_rows.append({
                        "sku": sku_choice,
                        "name": email_product_options[sku_choice],
                        "qty": qty,
                        "unit_cost": unit_cost,
                        "line_cost": line_cost,
                        "basis": basis_label,
                    })

            if st.button("➕ Add Product"):
                st.session_state["reorder_email_lines"].append(uuid.uuid4().hex[:8])
                st.rerun()

            total_cost = sum(r["line_cost"] for r in order_rows)
            st.metric("Total Cost", f"${total_cost:,.2f}")

            clinic_name = auth.get_clinic_name() or "our clinic"
            profile = auth.get_profile()
            staff_name = (profile or {}).get("full_name") or "Clinic Staff"
            contact_first = (vendor_row.get("contact_name") or "").split(" ")[0] or "there"
            lead_time = vendor_row.get("lead_time_days")

            if order_rows:
                product_lines = "\n".join(
                    f"- {r['name']} (SKU: {r['sku']}) — Qty: {r['qty']} (${r['line_cost']:,.2f})"
                    for r in order_rows
                )
            else:
                product_lines = "- [add a product and quantity above]"

            lead_time_line = ""
            if pd.notna(lead_time):
                lead_time_line = f"Our standard lead time expectation is {int(lead_time)} days. "

            subject = f"Reorder Request - {clinic_name}"
            body = (
                f"Hi {contact_first},\n\n"
                f"We'd like to place a reorder with {vendor_row['vendor_name']}. "
                f"Could you please send updated pricing and availability for the following item(s)?\n\n"
                f"{product_lines}\n\n"
                f"Estimated Total: ${total_cost:,.2f}\n\n"
                f"{lead_time_line}Please let us know if any items are back-ordered.\n\n"
                f"Thank you,\n{staff_name}\n{clinic_name}"
            )

            lines_signature = "_".join(f"{r['sku']}:{r['qty']}" for r in order_rows)
            draft_key = f"email_draft_body_{email_vendor_id}_{lines_signature}"
            draft_body = st.text_area(
                "Email draft (edit as needed, then send)",
                value=body,
                height=240,
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
