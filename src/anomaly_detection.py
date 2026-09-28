"""
src/anomaly_detection.py
--------------------------
Isolation Forest anomaly detection for invoices.

IDEA IN ONE PARAGRAPH (for your viva)
  Isolation Forest builds many random decision trees. Each tree keeps
  splitting the data on a random feature at a random value. Unusual points
  sit far from the crowd, so they get isolated in FEW splits (short path);
  normal points need MANY splits (long path). The average path length over
  all trees becomes the anomaly score. It needs no labelled fraud examples,
  which is why it suits invoices: we rarely know in advance which ones are bad.
"""

from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.features import FEATURE_COLUMNS

CONTAMINATION = 0.03   # ASSUMPTION: roughly 3% of invoices are unusual
N_ESTIMATORS = 200     # number of random trees
RANDOM_STATE = 42      # makes results reproducible


def train_isolation_forest(features: pd.DataFrame) -> dict:
    """
    Train the model.

    What it does : fits an Isolation Forest on the engineered features.
    Why needed   : the fitted forest is what scores every invoice.
    Input        : DataFrame containing all FEATURE_COLUMNS (one row/invoice).
    Output       : a 'bundle' dict with the model plus the metadata needed to
                   score consistently later (score range, training date, size).

    Note: tree models split on thresholds, so feature scaling is NOT needed.
    """
    X = features[FEATURE_COLUMNS].astype(float)
    model = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
    )
    model.fit(X)

    # score_samples returns NEGATIVE numbers (lower = more abnormal). We flip
    # the sign so that higher = more anomalous, then remember min/max so we
    # can rescale to an easy 0-1 range.
    raw = -model.score_samples(X)
    return {
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "score_min": float(raw.min()),
        "score_max": float(raw.max()),
        "n_samples": int(len(X)),
        "contamination": CONTAMINATION,
        "n_estimators": N_ESTIMATORS,
        "trained_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }


def score_invoices(bundle: dict, features: pd.DataFrame) -> pd.DataFrame:
    """
    Score invoices with a trained model.

    Input : the model bundle + feature DataFrame.
    Output: DataFrame with invoice_id, anomaly_score (0 = very normal,
            1 = most unusual), is_anomaly (True/False) and anomaly_reason.
    """
    X = features[bundle["feature_columns"]].astype(float)
    raw = -bundle["model"].score_samples(X)
    span = max(bundle["score_max"] - bundle["score_min"], 1e-9)
    score = np.clip((raw - bundle["score_min"]) / span, 0, 1)

    is_anomaly = bundle["model"].predict(X) == -1   # -1 means "anomaly"

    result = pd.DataFrame({
        "invoice_id": features["invoice_id"].values,
        "anomaly_score": score.round(4),
        "is_anomaly": is_anomaly,
    })
    result["anomaly_reason"] = explain_anomalies(features, is_anomaly)
    return result


def explain_anomalies(features: pd.DataFrame, is_anomaly: np.ndarray) -> list[str]:
    """
    Give each flagged invoice a plain-English reason.

    Isolation Forest itself does not say WHY a point is odd, so we compare
    each flagged invoice with the dataset's typical values on a few
    human-understandable features and report the ones that stand out most.
    Normal invoices get an empty reason.
    """
    reasons = []
    for (_, row), flagged in zip(features.iterrows(), is_anomaly):
        if not flagged:
            reasons.append("")
            continue
        found = []
        if row["amount_ratio"] >= 2.5:
            found.append(f"Amount is {row['amount_ratio']:.1f}x this vendor's typical invoice")
        elif row["amount_ratio"] <= 0.25:
            found.append(f"Amount is only {row['amount_ratio']:.2f}x this vendor's typical invoice")
        if row["effective_delay"] >= 20:
            found.append(f"Payment delay of {row['effective_delay']:.0f} days")
        if row["delay_deviation"] >= 15:
            found.append("Delay far above this vendor's usual pattern")
        if row["vendor_burst_7d"] >= 10:
            found.append(f"{int(row['vendor_burst_7d'])} invoices from this vendor within 2 weeks")
        reasons.append("; ".join(found) if found
                       else "Unusual combination of values across several features")
    return reasons
