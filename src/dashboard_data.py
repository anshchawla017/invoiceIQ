"""
src/dashboard_data.py
-----------------------
The data layer for the dashboard. It contains NO Streamlit code, so it can be
tested on its own.

    load_results()  -> one DataFrame: invoice + engineered features + risk
                       score/level/reasons + anomaly flag + anomaly reason.
    assemble()      -> the pure merge step (takes DataFrames, no database).
"""

from __future__ import annotations

import json

import pandas as pd

from src.anomaly_detection import explain_anomalies
from src.database import Invoice, engine, get_session, init_db
from src.duplicate_detection import detect_duplicates
from src.features import build_features, load_invoices_df
from src.init_demo_db import load_demo_dataset
from src.ml_models import run_full_analysis

MIN_INVOICES_FOR_ANALYSIS = 20   # Isolation Forest needs a reasonable sample


def count_invoices() -> int:
    init_db()
    session = get_session()
    try:
        return session.query(Invoice).count()
    finally:
        session.close()


def parse_reasons(value) -> list:
    """The reasons column is stored as JSON text; turn it back into a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except ValueError:
            return []
    return []


def assemble(features: pd.DataFrame, risk: pd.DataFrame, anomaly: pd.DataFrame) -> pd.DataFrame:
    """Merge features with the stored risk / anomaly results (pure pandas)."""
    df = features.merge(risk, on="invoice_id", how="left")
    df = df.merge(anomaly, on="invoice_id", how="left")

    df["analysed"] = df["risk_score"].notna()
    df["is_anomaly"] = df["is_anomaly"].map(lambda v: bool(v) if pd.notna(v) else False)
    df["risk_level"] = df["risk_level"].where(df["analysed"], "Not scored")
    df["risk_score"] = df["risk_score"].fillna(0.0)
    df["anomaly_score"] = df["anomaly_score"].fillna(0.0)
    df["reasons"] = df["reasons"].map(parse_reasons)

    # The anomaly reason text is not stored in SQL, so rebuild it from the
    # stored flag + the features (deterministic, same rules as Phase 3).
    df = df.join(detect_duplicates(df))       # same rules the analysis used
    df["anomaly_reason"] = explain_anomalies(df, df["is_anomaly"].values)
    df["month"] = df["invoice_date"].dt.to_period("M").astype(str)
    return df


def load_results() -> pd.DataFrame:
    """Everything the pages need, in one DataFrame. Empty if no invoices."""
    init_db()
    invoices = load_invoices_df(engine)
    if invoices.empty:
        return invoices
    features = build_features(invoices)
    risk = pd.read_sql("SELECT invoice_id, risk_score, risk_level, reasons FROM risk_predictions", engine)
    anomaly = pd.read_sql("SELECT invoice_id, anomaly_score, is_anomaly FROM anomaly_results", engine)
    return assemble(features, risk, anomaly)


def load_demo_and_analyse() -> dict:
    """Reset the database, load the demo CSV and run the ML pipeline."""
    load_demo_dataset()
    return run_full_analysis()
