"""views/model_center.py -- honest model statistics (no invented accuracy numbers)."""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.features import FEATURE_COLUMNS
from src.ml_models import load_anomaly_bundle, run_full_analysis
from src.risk_engine import FACTOR_LABELS, RISK_LEVELS, WEIGHTS
from src.ui import ensure_scored, kpi_row, note, page_header, style_fig


def render(df) -> None:
    page_header("Model Center", "How the detection model was set up and what it has learned from your data.")
    bundle = load_anomaly_bundle()
    if bundle is None:
        st.warning("No trained model yet. Load data first, or press the retrain button below.")
    else:
        kpi_row([
            ("Algorithm", "Isolation Forest", "unsupervised"),
            ("Trees", f"{bundle['n_estimators']}", "random isolation trees"),
            ("Contamination", f"{bundle['contamination']:.0%}", "assumed share of unusual invoices"),
            ("Trained on", f"{bundle['n_samples']:,}", f"invoices, {str(bundle['trained_at']).replace('T', ' ')}"),
        ])
    st.write("")

    if st.button("Retrain models on current data", key="retrain"):
        try:
            with st.spinner("Training..."):
                run_full_analysis()
            st.success("Models retrained and all invoices re-scored.")
            st.rerun()
        except Exception as exc:
            st.error(f"Retraining failed: {exc}")

    if not ensure_scored(df):
        return

    st.subheader("Features the Isolation Forest uses")
    flagged = df[df["is_anomaly"]]
    normal = df[~df["is_anomaly"]]
    stats = pd.DataFrame({
        "Feature": FEATURE_COLUMNS,
        "Average, normal invoices": [normal[c].mean() for c in FEATURE_COLUMNS],
        "Average, flagged invoices": [flagged[c].mean() if len(flagged) else float("nan") for c in FEATURE_COLUMNS],
    })
    st.dataframe(stats, hide_index=True, column_config={
        "Average, normal invoices": st.column_config.NumberColumn(format="%.2f"),
        "Average, flagged invoices": st.column_config.NumberColumn(format="%.2f"),
    })
    st.caption("These are real averages from your data. A big gap between the two columns "
               "shows which features drive the flags.")

    c1, c2 = st.columns(2)
    with c1:
        plot = df.assign(Result=df["is_anomaly"].map({True: "Flagged", False: "Normal"}))
        fig = px.histogram(plot, x="anomaly_score", nbins=30, color="Result",
                           color_discrete_map={"Flagged": "#ef4444", "Normal": "#3b5b8c"},
                           category_orders={"Result": ["Normal", "Flagged"]},
                           title="Anomaly score distribution")
        fig.update_layout(xaxis_title="Anomaly score (0 normal, 1 most unusual)", yaxis_title="Invoices")
        st.plotly_chart(style_fig(fig, 300))
    with c2:
        st.markdown("**Risk score weights**")
        st.table({"Factor": [FACTOR_LABELS[k] for k in WEIGHTS],
                  "Weight": [f"{v:.0%}" for v in WEIGHTS.values()]})
        st.markdown("**Levels:** " + ", ".join(f"{name} from {low}" for low, name in reversed(RISK_LEVELS)))

    st.subheader("Why there is no accuracy, precision or recall here")
    note("Those metrics compare predictions with confirmed answers (which invoices were truly fraudulent). "
         "This dataset has no such labels, so any number shown would be invented. The Isolation Forest is "
         "unsupervised and the risk score is a rule-based weighted sum. Both flag invoices for a human to "
         "review. With real labelled outcomes later, proper supervised metrics could be added.")
