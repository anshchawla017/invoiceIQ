"""views/vendors.py -- vendor intelligence: who we spend with, who pays late, who looks risky."""

import plotly.express as px
import streamlit as st

from src.analytics import vendor_summary
from src.ui import ensure_scored, kpi_row, level_label, money, page_header, style_fig


def render(df) -> None:
    page_header("Vendors", "Who you spend with, who gets paid late, and which vendors deserve a closer look.")
    ensure_scored(df)
    vs = vendor_summary(df)

    watch = vs[vs["watch"] != ""]
    kpi_row([
        ("Vendors", f"{len(vs)}", f"{len(df):,} invoices in total"),
        ("Vendors to watch", f"{len(watch)}", "at least one warning sign", "#f59e0b"),
        ("Late-paid vendors", f"{int((vs['avg_days_late'] > 10).sum())}", "average over 10 days late", "#f97316"),
        ("Top vendor share", f"{vs['share_of_spend'].iloc[0]:.0%}", vs["vendor_name"].iloc[0]),
    ])
    st.write("")

    fig = px.scatter(vs, x="avg_days_late", y="total_spend", size="invoices", color="avg_risk",
                     hover_name="vendor_name", color_continuous_scale="YlOrRd",
                     title="Vendors: spend vs lateness (bubble size = number of invoices)")
    fig.update_layout(xaxis_title="Average days paid late", yaxis_title="Total spend ($)",
                      coloraxis_colorbar_title="Avg risk")
    st.plotly_chart(style_fig(fig, 400))

    st.subheader("All vendors")
    only_watch = st.checkbox("Only vendors with a warning sign")
    vs = vs.assign(share_pct=vs["share_of_spend"] * 100)
    watch = vs[vs["watch"] != ""]
    table = watch if only_watch else vs
    st.dataframe(
        table[["vendor_name", "category", "invoices", "total_spend", "share_pct", "avg_days_late",
               "overdue", "anomalies", "possible_duplicates", "avg_risk", "watch"]],
        hide_index=True,
        column_config={
            "vendor_name": "Vendor", "category": "Main category", "invoices": "Invoices",
            "total_spend": st.column_config.NumberColumn("Total spend", format="$%.0f"),
            "share_pct": st.column_config.NumberColumn("Share of spend", format="%.1f%%"),
            "avg_days_late": st.column_config.NumberColumn("Avg days late", format="%.1f"),
            "overdue": "Overdue", "anomalies": "Anomalies", "possible_duplicates": "Duplicates",
            "avg_risk": st.column_config.NumberColumn("Avg risk", format="%.1f"),
            "watch": "Warning signs",
        },
    )
    st.caption("Warning signs are simple rules: average delay over 10 days, 3+ anomalies, 4+ possible "
               "duplicates, or more than 8% of total spend.")

    st.subheader("Vendor detail")
    names = dict(zip(vs["vendor_id"], vs["vendor_name"]))
    vid = st.selectbox("Choose a vendor", list(names), format_func=names.get)
    v = df[df["vendor_id"] == vid]
    row = vs[vs["vendor_id"] == vid].iloc[0]
    kpi_row([
        ("Total spend", money(row["total_spend"]), f"{int(row['invoices'])} invoices"),
        ("Average invoice", money(row["avg_amount"]), f"largest {money(v['amount'].max())}"),
        ("Avg days late", f"{row['avg_days_late']:.1f}", f"{int(row['overdue'])} overdue"),
        ("Highest risk score", f"{row['max_risk']:.1f}", f"{int(row['anomalies'])} anomalies", "#f97316"),
    ])
    monthly = v.groupby("month", as_index=False)["amount"].sum().sort_values("month")
    fig = px.bar(monthly, x="month", y="amount", title=f"{names[vid]}: invoice value by month",
                 color_discrete_sequence=["#38bdf8"])
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(style_fig(fig, 280, money_axis="y"))

    t = v.sort_values("risk_score", ascending=False).copy()
    t["risk_level"] = t["risk_level"].map(level_label)
    t["invoice_date"] = t["invoice_date"].dt.date
    st.dataframe(
        t[["invoice_id", "invoice_date", "amount", "payment_status", "effective_delay", "risk_score", "risk_level"]],
        hide_index=True,
        column_config={
            "invoice_id": "Invoice", "invoice_date": "Date", "payment_status": "Status", "risk_level": "Level",
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "effective_delay": st.column_config.NumberColumn("Days late", format="%.0f"),
            "risk_score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.1f"),
        },
    )
