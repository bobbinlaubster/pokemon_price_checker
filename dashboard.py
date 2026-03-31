from pathlib import Path

import streamlit as st

from src.dashboard_data import build_best_price_table, load_snapshot


st.set_page_config(page_title="PriceChecker Dashboard", layout="wide")
st.title("PriceChecker Dashboard")
st.caption("Compare current offers, price-per-pack, and optional market prices in one place.")

snapshot_default = Path("results/latest_snapshot.json")
sets_default = Path("sets.yaml")

snapshot_path = Path(st.sidebar.text_input("Latest snapshot JSON", str(snapshot_default)))
sets_path = Path(st.sidebar.text_input("Sets YAML", str(sets_default)))

if not snapshot_path.exists():
    st.warning("No latest snapshot found yet. Run `python price_checker.py` first.")
    st.stop()

snapshot_df = load_snapshot(str(snapshot_path))
best_df = build_best_price_table(str(snapshot_path), str(sets_path))

franchises = ["All"]
if not snapshot_df.empty and "franchise" in snapshot_df.columns:
    franchises += sorted(snapshot_df["franchise"].dropna().unique().tolist())
selected_franchise = st.sidebar.selectbox("Franchise", franchises)

stock_only = st.sidebar.checkbox("In stock only", value=True)

filtered_snapshot = snapshot_df.copy()
if selected_franchise != "All" and not filtered_snapshot.empty:
    filtered_snapshot = filtered_snapshot[filtered_snapshot["franchise"] == selected_franchise]
if stock_only and not filtered_snapshot.empty and "in_stock" in filtered_snapshot.columns:
    filtered_snapshot = filtered_snapshot[filtered_snapshot["in_stock"] == True]

filtered_best = best_df.copy()
if selected_franchise != "All" and not filtered_best.empty and "franchise" in filtered_best.columns:
    filtered_best = filtered_best[filtered_best["franchise"] == selected_franchise]

metric_cols = st.columns(3)
metric_cols[0].metric("Offers", int(len(filtered_snapshot.index)))
metric_cols[1].metric("Best Rows", int(len(filtered_best.index)))
metric_cols[2].metric("Sites", int(filtered_snapshot["site_name"].nunique()) if not filtered_snapshot.empty else 0)

st.subheader("Best Price by Set")
if filtered_best.empty:
    st.info("No best-price rows available yet.")
else:
    st.dataframe(
        filtered_best[
            [
                "franchise",
                "set_name",
                "product_type",
                "best_site",
                "best_price",
                "best_price_per_pack",
                "market_price",
                "delta_vs_market",
                "best_url",
            ]
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "best_url": st.column_config.LinkColumn("Buy Link", display_text="Open"),
        },
    )

st.subheader("All Current Offers")
if filtered_snapshot.empty:
    st.info("No offers match the current filters.")
else:
    st.dataframe(
        filtered_snapshot[
            [
                "franchise",
                "set_name",
                "product_type",
                "site_name",
                "price",
                "price_per_pack",
                "landed_price",
                "landed_price_per_pack",
                "pack_count",
                "in_stock",
                "sku_or_url",
            ]
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "sku_or_url": st.column_config.LinkColumn("Buy Link", display_text="Open"),
        },
    )
