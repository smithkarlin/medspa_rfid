import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import auth
import db
import ui

# ==============================================================
# PAGE CONFIG
# ==============================================================

# Design tokens now live in ui.py and are shared with every other page,
# so the whole app reads as one consistent platform.
INK = ui.INK
MUTED = ui.MUTED
BORDER = ui.BORDER
BLUE_1 = ui.BLUE_1
BLUE_2 = ui.BLUE_2
RED_EXPIRING = ui.RED_EXPIRING

render_kpi_card = ui.render_kpi_card


def render_analytics_page():
    ui.inject_base_css()
    ui.require_clinic()
    ui.render_sidebar_account()
    ui.render_page_header("📊 Dashboard", "Real-time clinical visibility, site filtering, and asset tracking powered by Tagmate.")

    try:
        # ==========================================================
        # LOAD DATA (fetched once per page load, filtered with pandas)
        # ==========================================================
        tagged_df = db.fetch_df(
            "tagged_inventory",
            columns=["epc", "sku", "product_name", "expiration_date", "lot_number",
                     "location", "status", "commissioned_at", "last_scanned_at"],
        )
        barcode_df = db.fetch_df(
            "barcode_inventory",
            columns=["id", "barcode", "product_name", "sku", "expiration_date",
                     "received_date", "unit_cost", "status", "location"],
        )
        catalog_df = db.fetch_df(
            "product_catalog",
            columns=["sku", "barcode", "product_name", "unit_cost", "reorder_level"],
        )

        tagged_df = tagged_df.merge(
            catalog_df[["sku", "product_name", "unit_cost"]].rename(columns={"product_name": "catalog_product_name"}),
            on="sku", how="left"
        )

        # ==========================================================
        # GLOBAL SITE / FACILITY FILTER
        # ==========================================================
        tagged_sites = tagged_df["location"].dropna()
        barcode_sites = barcode_df["location"].dropna()
        db_sites = sorted((set(tagged_sites) | set(barcode_sites)) - {""})
        all_sites = ["All Med Spa Sites"] + db_sites

        selected_site = st.selectbox(
            "Site / Location",
            all_sites,
            index=0,
            key="global_site_filter",
        )

        def filter_site(frame: pd.DataFrame) -> pd.DataFrame:
            if selected_site == "All Med Spa Sites":
                return frame
            return frame[frame["location"] == selected_site]

        tagged_filtered = filter_site(tagged_df)
        barcode_filtered = filter_site(barcode_df)

        tagged_in_stock = tagged_filtered[tagged_filtered["status"] == "In Stock"]
        barcode_in_stock = barcode_filtered[barcode_filtered["status"] == "In Stock"]

        # ==========================================================
        # 1. CLEAN GRADIENT KPI CARDS
        # ==========================================================
        total_rfid_items = len(tagged_in_stock)
        total_barcode_items = len(barcode_in_stock)
        total_in_stock = total_rfid_items + total_barcode_items

        rfid_val = float(tagged_in_stock["unit_cost"].fillna(0.0).sum())
        barcode_val = float(barcode_in_stock["unit_cost"].fillna(0.0).sum())
        total_inventory_value = rfid_val + barcode_val

        unique_products = len(set(tagged_in_stock["sku"]) | set(barcode_in_stock["sku"]))

        exp_dt_kpi = pd.to_datetime(barcode_in_stock["expiration_date"], errors="coerce")
        days_out = (exp_dt_kpi - pd.Timestamp.now().normalize()).dt.days
        expiring_soon = int(((days_out <= 30) & exp_dt_kpi.notna()).sum())

        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

        with kpi_col1:
            render_kpi_card("Items In Stock", f"{total_in_stock:,}")
        with kpi_col2:
            render_kpi_card("Total Stock Value", f"${total_inventory_value:,.0f}")
        with kpi_col3:
            render_kpi_card("Active SKUs", f"{unique_products:,}")
        with kpi_col4:
            render_kpi_card("Expiring <= 30 Days", f"{expiring_soon:,}")

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

        # ==========================================================
        # 2. QUANTITY BY PRODUCT / TYPE BAR CHARTS
        # ==========================================================
        col_left, col_right = st.columns([1, 1], gap="medium")

        df_rfid = pd.DataFrame({
            "product": tagged_in_stock["catalog_product_name"].fillna(tagged_in_stock["sku"]),
            "sku": tagged_in_stock["sku"],
            "expiration_date": pd.NA,
            "source": "RFID",
        })

        df_bc = pd.DataFrame({
            "product": barcode_in_stock["product_name"].fillna(barcode_in_stock["sku"]),
            "sku": barcode_in_stock["sku"],
            "expiration_date": barcode_in_stock["expiration_date"],
            "source": "Barcode",
        })

        df_combined = pd.concat([df_rfid, df_bc], ignore_index=True)

        with col_left:
            with st.container(border=True):
                st.markdown('<div class="tm-panel-title">Units Remaining by Product (Top 10)</div>', unsafe_allow_html=True)

                if not df_combined.empty:
                    today = pd.to_datetime('today').normalize()
                    df_combined['exp_dt'] = pd.to_datetime(df_combined['expiration_date'], errors='coerce')
                    df_combined['is_expiring_30d'] = (df_combined['exp_dt'].notnull()) & ((df_combined['exp_dt'] - today).dt.days <= 30)

                    grouped = df_combined.groupby('product').agg(
                        total_units=('product', 'count'),
                        expiring_units=('is_expiring_30d', 'sum')
                    ).reset_index()

                    grouped['healthy_units'] = grouped['total_units'] - grouped['expiring_units']

                    top_10 = grouped.sort_values(by='total_units', ascending=False).head(10)
                    top_10 = top_10.sort_values(by='total_units', ascending=True)

                    fig_top = go.Figure()

                    fig_top.add_trace(go.Bar(
                        y=top_10['product'],
                        x=top_10['healthy_units'],
                        name='Healthy Stock',
                        orientation='h',
                        marker=dict(color=BLUE_2),
                    ))

                    fig_top.add_trace(go.Bar(
                        y=top_10['product'],
                        x=top_10['expiring_units'],
                        name='Expiring ≤ 30 Days',
                        orientation='h',
                        marker=dict(color=RED_EXPIRING),
                    ))

                    fig_top.update_layout(
                        barmode='stack',
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", color=INK, size=11),
                        margin=dict(l=10, r=20, t=10, b=10),
                        height=280,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        xaxis=dict(title="Quantity in Stock", showgrid=True, gridcolor=BORDER),
                        yaxis=dict(showgrid=False),
                    )

                    st.plotly_chart(fig_top, use_container_width=True)
                else:
                    st.info("No items currently in stock for this location.")

        with col_right:
            with st.container(border=True):
                st.markdown('<div class="tm-panel-title">Units Remaining by Tracking Type</div>', unsafe_allow_html=True)

                if not df_combined.empty:
                    type_counts = df_combined['source'].value_counts().reset_index()
                    type_counts.columns = ['Tracking Type', 'Units Left']

                    fig_type = go.Figure(go.Bar(
                        x=type_counts['Tracking Type'],
                        y=type_counts['Units Left'],
                        marker=dict(color=[BLUE_2, BLUE_1]),
                        text=type_counts['Units Left'],
                        textposition='auto',
                        width=0.4
                    ))
                    fig_type.update_layout(
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", color=INK, size=12),
                        margin=dict(l=10, r=10, t=10, b=10),
                        height=280,
                        yaxis=dict(title="Total Units", showgrid=True, gridcolor=BORDER),
                        xaxis=dict(showgrid=False)
                    )
                    st.plotly_chart(fig_type, use_container_width=True)
                else:
                    st.info("No tracking data available for this location.")

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

        # ==========================================================
        # 3. EXPIRATION RISK TABLE
        # ==========================================================
        with st.container(border=True):
            header_col, dl_col = st.columns([5, 1])
            with header_col:
                st.markdown('<div class="tm-panel-title">Items Nearing Expiration</div>', unsafe_allow_html=True)

            df_full = barcode_filtered[
                (barcode_filtered["status"] == "In Stock") & (barcode_filtered["expiration_date"].notna())
            ][["barcode", "product_name", "sku", "expiration_date", "unit_cost", "location"]].rename(columns={
                "barcode": "Barcode",
                "product_name": "Product Name",
                "sku": "SKU",
                "expiration_date": "Expiration Date",
                "unit_cost": "Cost ($)",
                "location": "Location",
            })

            if not df_full.empty:
                df_full['exp_dt'] = pd.to_datetime(df_full['Expiration Date'], errors='coerce')
                today = pd.to_datetime('today').normalize()
                df_full['Days to Expire'] = (df_full['exp_dt'] - today).dt.days
                df_expiring = df_full[df_full['Days to Expire'] <= 90].sort_values(by='Days to Expire')

                if not df_expiring.empty:
                    def risk_tag(days):
                        if days < 0:
                            return "Expired"
                        elif days <= 30:
                            return "Critical"
                        else:
                            return "Warning"

                    df_expiring['Status'] = df_expiring['Days to Expire'].apply(risk_tag)

                    with dl_col:
                        st.download_button(
                            "⬇ Export",
                            data=df_expiring.drop(columns=['exp_dt']).to_csv(index=False),
                            file_name="expiring_inventory.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )

                    st.dataframe(
                        df_expiring[[
                            'Status', 'Barcode', 'Product Name', 'Expiration Date',
                            'Days to Expire', 'Cost ($)', 'Location'
                        ]].style.format({'Cost ($)': '${:,.2f}'}),
                        use_container_width=True,
                        height=280,
                    )
                else:
                    st.success("All clear — no barcode inventory expiring within 90 days at this site.")
            else:
                st.info("No barcode inventory records found for this location selection.")

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

        # ==========================================================
        # 4. REORDER RECOMMENDATIONS
        # ==========================================================
        with st.container(border=True):
            st.markdown('<div class="tm-panel-title">Reorder Recommendations</div>', unsafe_allow_html=True)
            st.caption(
                "Suggested order quantities based on how fast each product has been used "
                "(mark items 'Used' on the Checkout page to build this history)."
            )

            reco_df = db.get_reorder_recommendations()
            if reco_df.empty:
                st.info("Add products to your catalog to see reorder recommendations.")
            else:
                reco_vendors_df = db.get_vendors_df()
                vendor_name_lookup = (
                    dict(zip(reco_vendors_df["id"], reco_vendors_df["vendor_name"]))
                    if not reco_vendors_df.empty else {}
                )
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
                        "'Used' on the Checkout page as you go through stock, and these numbers will fill in."
                    )
                st.caption("Ready to order? Head to the **Vendors** page to draft a reorder email.")

    except Exception as e:
        st.error(f"Database Read Error: {e}")


if __name__ == "__main__":
    render_analytics_page()
