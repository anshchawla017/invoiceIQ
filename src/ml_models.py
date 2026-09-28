"""
src/ml_models.py
------------------
Orchestrates the whole ML pipeline and handles saving/loading.

    SQL invoices -> features -> Isolation Forest -> risk engine
                 -> results written back to SQL + models saved to models/

Run from the project root:
    python -m src.ml_models
"""

from __future__ import annotations

import json
import os

import joblib

from src.anomaly_detection import score_invoices, train_isolation_forest
from src.duplicate_detection import detect_duplicates
from src.database import AnomalyResult, RiskPrediction, engine, get_session, init_db
from src.features import build_features, load_invoices_df
from src.risk_engine import RISK_LEVELS, WEIGHTS, score_risk

MODELS_DIR = "models"
ANOMALY_MODEL_PATH = os.path.join(MODELS_DIR, "anomaly_model.pkl")
RISK_MODEL_PATH = os.path.join(MODELS_DIR, "risk_model.pkl")


def save_models(anomaly_bundle: dict) -> None:
    """Persist the trained anomaly bundle and the risk-engine configuration
    (weights + thresholds) with joblib, so the app can reload them without
    retraining."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(anomaly_bundle, ANOMALY_MODEL_PATH)
    joblib.dump({
        "type": "rule-based weighted score (not a trained classifier)",
        "weights": WEIGHTS,
        "risk_levels": RISK_LEVELS,
    }, RISK_MODEL_PATH)


def load_anomaly_bundle():
    """Return the saved anomaly bundle, or None if it has not been trained."""
    if not os.path.exists(ANOMALY_MODEL_PATH):
        return None
    try:
        return joblib.load(ANOMALY_MODEL_PATH)
    except Exception:
        return None   # corrupted file -> caller can simply retrain


def _write_results(anomaly_df, risk_df) -> None:
    """Replace the contents of anomaly_results and risk_predictions."""
    session = get_session()
    try:
        session.query(AnomalyResult).delete()
        session.query(RiskPrediction).delete()
        session.bulk_insert_mappings(AnomalyResult, [
            {"invoice_id": r.invoice_id, "anomaly_score": float(r.anomaly_score),
             "is_anomaly": bool(r.is_anomaly)}
            for r in anomaly_df.itertuples()
        ])
        session.bulk_insert_mappings(RiskPrediction, [
            {"invoice_id": r.invoice_id, "risk_score": float(r.risk_score),
             "risk_level": r.risk_level, "reasons": json.dumps(r.reasons)}
            for r in risk_df.itertuples()
        ])
        session.commit()
    except Exception as exc:
        session.rollback()
        raise RuntimeError(f"Could not save analysis results: {exc}") from exc
    finally:
        session.close()


def run_full_analysis() -> dict:
    """
    Run the entire pipeline on whatever invoices are in the database.

    Returns a summary dict for the UI (counts per risk level, anomalies
    found, model settings). Raises ValueError with a friendly message when
    the database is empty.
    """
    init_db()
    invoices = load_invoices_df(engine)
    features = build_features(invoices)          # raises ValueError if empty

    bundle = train_isolation_forest(features)
    anomaly_df = score_invoices(bundle, features)
    dup = detect_duplicates(features)
    features = features.join(dup)               # adds duplicate_score, duplicate_of
    risk_df = score_risk(features, anomaly_df, duplicate_score=dup["duplicate_score"].values)

    _write_results(anomaly_df, risk_df)
    save_models(bundle)

    levels = risk_df["risk_level"].value_counts().to_dict()
    return {
        "invoices_analysed": int(len(features)),
        "anomalies_found": int(anomaly_df["is_anomaly"].sum()),
        "possible_duplicates": int((dup["duplicate_score"] > 0).sum()),
        "risk_levels": {k: int(levels.get(k, 0)) for k in ("Low", "Medium", "High", "Critical")},
        "contamination": bundle["contamination"],
        "n_estimators": bundle["n_estimators"],
        "trained_at": bundle["trained_at"],
    }


if __name__ == "__main__":
    print(json.dumps(run_full_analysis(), indent=2))
