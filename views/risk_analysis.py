"""views/risk_analysis.py -- risk distribution + the 'Why was this flagged?' panel."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.risk_engine import FACTOR_LABELS, WEIGHTS
from src.ui import detail_list, ensure_scored, level_label, page_header, risk_ring, style_fig


def render(df) -> None:
    page_header("Risk Analysis", "Pick any invoice to see its risk score and exactly which warning signs added up to it.")
    if not ensure_scored(df):
        return

    fig = px.histogram(df, x="risk_score", nbins=25, title="How risk scores are spread",
                       color_discrete_sequence=["#38bdf8"])
    fig.update_layout(xaxis_title="Risk score (0-100)", yaxis_title="Invoices")
    st.plotly_chart(style_fig(fig, 280))

    st.subheader("Why was this flagged?")
    ranked = df.sort_values("risk_score", ascending=False)
    labels = {r.invoice_id: f"{r.invoice_id}  |  {r.vendor_name}  |  {r.risk_score:.1f}  {level_label(r.risk_level)}"
              for r in ranked.itertuples()}
    choice = st.selectbox("Choose an invoice (highest risk first; type to search)", list(labels), format_func=labels.get)
    row = df[df["invoice_id"] == choice].iloc[0]

    left, right = st.columns([2, 3])
    with left:
        risk_ring(float(row["risk_score"]), row["risk_level"])
        detail_list([
            ("Vendor", row["vendor_name"]),
            ("Amount", f"${row['amount']:,.2f}"),
            ("Status", row["payment_status"]),
            ("Due date", f"{row['due_date']:%d %b %Y}"),
            ("Days late", f"{row['effective_delay']:.0f}"),
            ("Anomaly model", "flagged" if row["is_anomaly"] else "not flagged"),
        ])
    with right:
        reasons = row["reasons"]
        if not reasons:
            st.success("No single risk factor contributed 3 or more points, so nothing stands out about this invoice.")
        else:
            fig = go.Figure(go.Bar(
                x=[r["points"] for r in reversed(reasons)], y=[r["label"] for r in reversed(reasons)],
                orientation="h", marker_color="#38bdf8",
                text=[f"{r['points']:.1f}" for r in reversed(reasons)], textposition="outside"))
            fig.update_layout(title="Points contributed by each factor", xaxis_title="Points (of 100)")
            st.plotly_chart(style_fig(fig, 60 + 55 * len(reasons)))
            for r in reasons:
                st.markdown(f'<div class="reason"><span class="pts">+{r["points"]:.1f}</span>'
                            f'<b>{r["label"]}</b><br>{r["text"]}</div>', unsafe_allow_html=True)
        if row["is_anomaly"]:
            st.markdown(f"**Anomaly model says:** {row['anomaly_reason']}")

    with st.expander("How is the score calculated?"):
        st.write("The score is a weighted sum of six factors, each between 0 and 1. It is a transparent "
                 "rule-based score, not a trained fraud classifier. It marks invoices worth a human look; "
                 "it does not prove wrongdoing.")
        st.table({"Factor": [FACTOR_LABELS[k] for k in WEIGHTS],
                  "Maximum points": [round(v * 100) for v in WEIGHTS.values()]})
        st.caption("A duplicate match alone is worth at most 15 points, so on its own it lands in Low or Medium.")
