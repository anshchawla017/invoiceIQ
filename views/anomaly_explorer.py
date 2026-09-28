"""views/anomaly_explorer.py -- what the Isolation Forest flagged, and why."""

import plotly.express as px
import streamlit as st

from src.ui import ensure_scored, kpi_row, level_label, money, page_header, style_fig


def render(df) -> None:
    page_header("Anomaly Explorer", "Invoices the model found unusual compared with the rest, and what made them stand out.")
    if not ensure_scored(df):
        return

    flagged = df[df["is_anomaly"]]
    kpi_row([
        ("Unusual invoices", f"{len(flagged):,}", f"{len(flagged) / len(df):.1%} of all invoices", "#f59e0b"),
        ("Value of unusual invoices", money(flagged["amount"].sum()), "sum of amounts"),
        ("Unusual but Low risk", f"{int((flagged['risk_level'] == 'Low').sum())}",
         "unusual, yet not late or repeated"),
    ])
    st.write("")

    plot = df.copy()
    plot["Status"] = plot["is_anomaly"].map({True: "Flagged", False: "Normal"})
    plot["Amount vs vendor's typical"] = plot["amount_ratio"].clip(lower=0.001)
    fig = px.scatter(plot, x="effective_delay", y="Amount vs vendor's typical", color="Status", log_y=True,
                     color_discrete_map={"Flagged": "#ef4444", "Normal": "#3b5b8c"},
                     hover_data=["invoice_id", "vendor_name", "amount"],
                     category_orders={"Status": ["Normal", "Flagged"]},
                     title="Flagged invoices vs the rest (log scale)")
    fig.update_traces(marker=dict(size=7, opacity=0.8))
    fig.update_layout(xaxis_title="Days late (or days overdue if unpaid)",
                      yaxis_title="Amount / vendor's typical amount (1 = typical)")
    st.plotly_chart(style_fig(fig, 420))

    st.subheader("Unusual invoices")
    if flagged.empty:
        st.info("The model did not flag any invoices.")
        return
    table = flagged.sort_values("anomaly_score", ascending=False).copy()
    table["risk_level"] = table["risk_level"].map(level_label)
    table["invoice_date"] = table["invoice_date"].dt.date
    st.dataframe(
        table[["invoice_id", "vendor_name", "invoice_date", "amount", "anomaly_score",
               "risk_score", "risk_level", "anomaly_reason"]],
        hide_index=True,
        column_config={
            "invoice_id": "Invoice", "vendor_name": "Vendor", "invoice_date": "Date", "risk_level": "Level",
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "anomaly_score": st.column_config.ProgressColumn("Anomaly score", min_value=0, max_value=1, format="%.2f"),
            "risk_score": st.column_config.NumberColumn("Risk score", format="%.1f"),
            "anomaly_reason": "Why it stands out",
        },
    )
    st.caption("An anomaly is a statistical oddity, not proof of a problem. "
               "'Unusual combination of values' means no single feature is extreme on its own.")
