"""views/analytics.py -- executive insights + spending, category and payment analytics."""

import plotly.express as px
import streamlit as st

from src.analytics import aging_summary, category_summary, concentration, monthly_summary
from src.insights import generate_insights
from src.ui import ensure_scored, finding_card, kpi_row, money, page_header, style_fig

def render_insights(df, limit=None) -> None:
    items = generate_insights(df)
    for i, (sev, head, detail) in enumerate(items[:limit] if limit else items):
        st.markdown(finding_card(sev, head, detail, i), unsafe_allow_html=True)


def render(df) -> None:
    page_header("Analytics", "Spending over time, where the money goes, and what is still unpaid.")
    ensure_scored(df)

    st.subheader("Key findings")
    render_insights(df)
    st.caption("Each finding is worked out from your data by fixed rules, so you can always trace it back to numbers.")

    monthly = monthly_summary(df)
    kpi_row([
        ("Months covered", f"{len(monthly)}", f"{monthly['month'].iloc[0]} to {monthly['month'].iloc[-1]}"),
        ("Average per month", money(monthly["value"].mean()), f"{monthly['invoices'].mean():.0f} invoices"),
        ("Top-5 vendor share", f"{concentration(df, 5):.0%}", "of total spend"),
    ])
    st.write("")

    fig = px.line(monthly, x="month", y="value", markers=True, title="Invoice value by month",
                  color_discrete_sequence=["#38bdf8"])
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(style_fig(fig, 320, money_axis="y"))
    st.caption("The most recent month may be incomplete, which would make it look like a drop.")

    c1, c2 = st.columns(2)
    with c1:
        cat = category_summary(df)
        fig = px.bar(cat.sort_values("value"), x="value", y="category", orientation="h",
                     title="Spend by category", color_discrete_sequence=["#38bdf8"])
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(style_fig(fig, money_axis="x"))
    with c2:
        aging = aging_summary(df)
        fig = px.bar(aging, x="bucket", y="value", text="invoices", title="Unpaid invoices by days past due",
                     color_discrete_sequence=["#f97316"])
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(style_fig(fig, money_axis="y"))
        st.caption("Labels show the number of invoices. Days past due are counted to the latest date in the data.")

    paid = df[df["payment_date"].notna()]
    if len(paid):
        fig = px.histogram(paid, x="effective_delay", nbins=40, title="How late are paid invoices?",
                           color_discrete_sequence=["#38bdf8"])
        fig.update_layout(xaxis_title="Days after due date (negative = paid early)", yaxis_title="Invoices")
        st.plotly_chart(style_fig(fig, 300))
