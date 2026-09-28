"""views/dashboard.py -- the overview: key numbers, key findings, and charts."""

import plotly.express as px
import streamlit as st

from src.ui import (ACCENT, LEVEL_ORDER, RISK_COLORS, STATUS_COLORS, ensure_scored, kpi_row,
                    level_label, money, page_header, style_fig)
from views.analytics import render_insights


def render(df) -> None:
    page_header("Dashboard", "Where your invoices stand right now, and what needs a look first.")
    ensure_scored(df)

    total = len(df)
    flagged = int(df["is_anomaly"].sum())
    high_crit = int(df["risk_level"].isin(["High", "Critical"]).sum())
    overdue = df[df["payment_status"] == "Overdue"]
    kpi_row([
        ("Invoices", f"{total:,}", f"from {df['vendor_id'].nunique()} vendors"),
        ("Total value", money(df["amount"].sum()), f"average {money(df['amount'].mean())}"),
        ("Unusual invoices", f"{flagged:,}", f"{flagged / total:.1%} flagged by the model", "#f59e0b",
         "Invoices the anomaly model found unusual compared with the rest"),
        ("High or Critical risk", f"{high_crit:,}", "risk score 60 or more", "#ef4444",
         "Invoices whose combined warning signs add up to 60 or more out of 100"),
        ("Overdue", money(overdue["amount"].sum()), f"{len(overdue)} unpaid invoices", "#f97316"),
    ])

    st.subheader("What needs attention")
    render_insights(df, limit=4)
    st.caption("More findings are on the Analytics page. Each one is worked out directly from your data.")

    c1, c2 = st.columns([3, 2])
    with c1:
        monthly = df.groupby("month", as_index=False)["amount"].sum().sort_values("month")
        fig = px.bar(monthly, x="month", y="amount", title="Invoice value by month",
                     color_discrete_sequence=[ACCENT])
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(style_fig(fig, money_axis="y"))
    with c2:
        status = df["payment_status"].value_counts().reset_index()
        status.columns = ["status", "count"]
        fig = px.pie(status, names="status", values="count", hole=0.55, title="Payment status",
                     color="status", color_discrete_map=STATUS_COLORS)
        st.plotly_chart(style_fig(fig))

    c3, c4 = st.columns(2)
    with c3:
        levels = df["risk_level"].value_counts().reindex(LEVEL_ORDER, fill_value=0).reset_index()
        levels.columns = ["risk_level", "invoices"]
        fig = px.bar(levels, x="risk_level", y="invoices", title="Invoices by risk level",
                     color="risk_level", color_discrete_map=RISK_COLORS, text="invoices")
        fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(style_fig(fig))
    with c4:
        top = (df.groupby("vendor_name", as_index=False)["amount"].sum()
                 .nlargest(10, "amount").sort_values("amount"))
        fig = px.bar(top, x="amount", y="vendor_name", orientation="h", title="Top 10 vendors by spend",
                     color_discrete_sequence=[ACCENT])
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(style_fig(fig, money_axis="x"))

    st.subheader("Ten highest-risk invoices")
    top_risk = df.sort_values("risk_score", ascending=False).head(10).copy()
    top_risk["invoice_date"] = top_risk["invoice_date"].dt.date
    top_risk["risk_level"] = top_risk["risk_level"].map(level_label)
    st.dataframe(
        top_risk[["invoice_id", "vendor_name", "invoice_date", "amount", "payment_status",
                  "risk_score", "risk_level"]],
        hide_index=True,
        column_config={
            "invoice_id": "Invoice", "vendor_name": "Vendor", "invoice_date": "Date",
            "payment_status": "Status", "risk_level": "Level",
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "risk_score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.1f"),
        },
    )
    st.caption("Open **Risk Analysis** in the sidebar to see why an invoice got its score.")
