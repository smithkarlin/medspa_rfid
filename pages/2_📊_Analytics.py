import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import db

# ==============================================================
# PAGE CONFIG
# ==============================================================
st.set_page_config(page_title="tagmate Analytics", page_icon="◆", layout="wide")

# ==============================================================
# DESIGN TOKENS
# ==============================================================
BG = "#F4F6FA"
CARD = "#FFFFFF"
INK = "#2B3445"
MUTED = "#8A93A6"
BORDER = "#EDF0F5"

BLUE_1 = "#5B9BF7"
BLUE_2 = "#3B6FE0"
RED_EXPIRING = "#F0664E"

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; color: {INK}; }}
.stApp {{ background-color: {BG}; }}

/* Suppress accidental empty element spaces */
div[data-testid="stElementContainer"]:empty {{ display: none !important; }}

.tm-title {{ font-family: 'Poppins', sans-serif; font-weight: 600; font-size: 2.1rem; color: {INK}; margin: 0; }}
.tm-caption {{ color: {MUTED}; font-size: 0.95rem; margin-top: 0.15rem; margin-bottom: 1.5rem; }}

/* ---- Gradient KPI cards ---- */
.tm-kpi-card {{
    position: relative;
    overflow: hidden;
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    background: linear-gradient(135deg, {BLUE_1} 0%, {BLUE_2} 100%);
    box-shadow: 0 8px 20px rgba(59,111,224,0.20);
    min-height: 110px;
    margin-bottom: 0.5rem;
}}
.tm-kpi-label {{
    font-family: 'Inter', sans-serif; 
    font-weight: 600; 
    font-size: 0.72rem;
    letter-spacing: 0.08em; 
    text-transform: uppercase; 
    color: rgba(255,255,255,0.85);
    margin-bottom: 0.4rem;
}}
.tm-kpi-value {{ 
    font-family: 'Poppins', sans-serif; 
    font-weight: 700; 
    font-size: 1.8rem; 
    color: #FFFFFF; 
    line-height: 1.1;
}}
.tm-kpi-wave {{ position: absolute; left: 0; right: 0; bottom: -2px; z-index: 1; opacity: 0.45; pointer-events: none; }}

.tm-panel-title {{ font-family: 'Poppins', sans-serif; font-weight: 600; font-size: 1.15rem; color: {INK}; margin: 0 0 0.5rem 0; }}

div[data-baseweb="select"] > div {{ border-radius: 10px !important; border-color: {BORDER} !important; }}
.stDataFrame {{ border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden; }}
</style>
"""

WAVE_SVG = """
<svg class="tm-kpi-wave" viewBox="0 0 300 60" preserveAspectRatio="none" width="100%" height="45">
  <path d="M0,35 C25,10 50,55 75,32 C100,10 125,50 150,30 C175,12 200,48 225,28 C250,12 275,45 300,25"
        fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
</svg>
"""


def render_kpi_card(label: str, value: str):
    html = f"""<div class="tm-kpi-card"><div class="tm-kpi-label">{label}</div><div class="tm-kpi-value">{value}</div>{WAVE_SVG}</div>"""
    st.markdown(html, unsafe_allow_html=True)


def render_analytics_page():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    st.markdown(
        """
        <h1 class="tm-title">Dashboard</h1>
        <div class="tm-caption">Real-time clinical visibility, site filtering, and asset tracking powered by tagmate.</div>
        """,
        unsafe_allow_html=True,
    )

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

    except Exception as e:
        st.error(f"Database Read Error: {e}")


if __name__ == "__main__":
    render_analytics_page()
