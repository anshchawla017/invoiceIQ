"""views/invoices.py -- searchable, filterable invoice table with CSV export."""

import streamlit as st

from src.ui import LEVEL_ORDER, count_chip, empty_state, level_label, page_header, panel_mark


def render(df) -> None:
    page_header("Invoices", "Search, filter and export every invoice. The riskiest appear first.")

    with st.container(border=True):
        panel_mark()
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        search = c1.text_input("Search invoice ID or vendor", placeholder="e.g. INV-00695 or Copperleaf")
        status = c2.multiselect("Payment status", sorted(df["payment_status"].unique()))
        levels = c3.multiselect("Risk level", LEVEL_ORDER)
        cats = c4.multiselect("Category", sorted(df["category"].dropna().unique()))
        only_flagged = st.checkbox("Only anomalies flagged by the model")

        lo, hi = float(df["amount"].min()), float(df["amount"].max())
        amount_range = st.slider("Amount range ($)", lo, hi, (lo, hi)) if hi > lo else (lo, hi)

    view = df
    if search:
        s = search.strip().lower()
        view = view[view["invoice_id"].str.lower().str.contains(s, regex=False)
                    | view["vendor_name"].str.lower().str.contains(s, regex=False)]
    if status:
        view = view[view["payment_status"].isin(status)]
    if levels:
        view = view[view["risk_level"].isin(levels)]
    if cats:
        view = view[view["category"].isin(cats)]
    if only_flagged:
        view = view[view["is_anomaly"]]
    view = view[view["amount"].between(*amount_range)]

    count_chip(len(view), len(df))
    if view.empty:
        empty_state("No invoices match these filters", "Try removing one, or click the x on a filter above.")
        return

    table = view.sort_values("risk_score", ascending=False).copy()
    table["risk_level"] = table["risk_level"].map(level_label)
    table["possible_duplicate"] = table["duplicate_score"] > 0
    for col in ("invoice_date", "due_date", "payment_date"):
        table[col] = table[col].dt.date
    table = table[["invoice_id", "vendor_name", "category", "invoice_date", "due_date", "amount",
                   "payment_status", "effective_delay", "risk_score", "risk_level", "is_anomaly", "possible_duplicate"]]
    st.dataframe(
        table, hide_index=True,
        column_config={
            "invoice_id": "Invoice", "vendor_name": "Vendor", "category": "Category",
            "invoice_date": "Date", "due_date": "Due", "payment_status": "Status", "risk_level": "Level",
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "effective_delay": st.column_config.NumberColumn("Days late", format="%.0f"),
            "risk_score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.1f"),
            "is_anomaly": st.column_config.CheckboxColumn("Anomaly"),
            "possible_duplicate": st.column_config.CheckboxColumn("Duplicate?"),
        },
    )
    st.download_button("Download filtered invoices (CSV)", table.to_csv(index=False).encode("utf-8"),
                       file_name="invoiceiq_filtered_invoices.csv", mime="text/csv")
