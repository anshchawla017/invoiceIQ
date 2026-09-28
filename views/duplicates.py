"""views/duplicates.py -- invoices that look like the same bill entered twice."""

import streamlit as st

from src.ui import ensure_scored, kpi_row, money, note, page_header

STRENGTH = {1.0: "Exact", 0.8: "Strong", 0.5: "Weak"}


def render(df) -> None:
    page_header("Duplicates", "Invoices that look like the same bill entered twice, so nothing gets paid double.")
    ensure_scored(df)

    dup = df[df["duplicate_score"] > 0].copy()
    if dup.empty:
        st.success("No possible duplicates found. Every invoice looks different from the others.")
        return
    dup["match"] = dup["duplicate_score"].map(STRENGTH)

    exact_strong = dup[dup["duplicate_score"] >= 0.8]
    kpi_row([
        ("Invoices involved", f"{len(dup)}", "both sides of each pair are marked", "#f59e0b"),
        ("Exact + strong matches", f"{len(exact_strong)}", money(exact_strong["amount"].sum()), "#ef4444"),
        ("Weak matches", f"{int((dup['duplicate_score'] < 0.8).sum())}", "amounts within 1%, 3 days", "#64748b"),
    ])
    st.write("")

    keep = st.multiselect("Match strength", ["Exact", "Strong", "Weak"], default=["Exact", "Strong"])
    view = dup[dup["match"].isin(keep)].sort_values(["vendor_name", "amount", "invoice_date"]).copy()
    view["invoice_date"] = view["invoice_date"].dt.date
    st.dataframe(
        view[["invoice_id", "vendor_name", "invoice_date", "amount", "payment_status", "match",
              "duplicate_of", "risk_score"]],
        hide_index=True,
        column_config={
            "invoice_id": "Invoice", "vendor_name": "Vendor", "invoice_date": "Date", "payment_status": "Status",
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "match": "Match", "duplicate_of": "Matches invoice(s)",
            "risk_score": st.column_config.NumberColumn("Risk score", format="%.1f"),
        },
    )
    note("Exact = same vendor, same amount to the cent, same date. Strong = same amount within 0.1% and within "
         "7 days. Weak = amount within 1% and within 3 days, which can happen by chance for vendors that send "
         "many invoices. This checks amount and date only, so repeating bills can be flagged wrongly. A person "
         "should confirm each one before anything is rejected.")
