"""
src/risk_engine.py
--------------------
Turns several warning signals into ONE 0-100 risk score per invoice, and
keeps the reasons so the user can see why.

IMPORTANT HONESTY NOTE
  This is a transparent, rule-based weighted score, NOT a trained fraud
  classifier. We have no confirmed-fraud labels, so a supervised model would
  have nothing real to learn from. A weighted score is easier to explain and
  every point of risk can be traced to a named factor. It flags invoices
  that deserve a human look; it does not prove wrongdoing.

Score = 100 x  sum( weight_i x component_i ),  each component in [0, 1].
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Weights must add up to 1.0 so the maximum possible score is exactly 100.
WEIGHTS = {
    "amount": 0.25,          # invoice much larger than vendor's norm
    "delay": 0.20,           # payment late / overdue
    "anomaly": 0.20,         # Isolation Forest anomaly score
    "duplicate": 0.15,       # possible duplicate (src/duplicate_detection.py)
    "vendor_history": 0.10,  # vendor is a habitual late payer
    "frequency": 0.10,       # vendor invoices unusually often
}

# (score lower bound, label) - checked from highest to lowest
RISK_LEVELS = [(80, "Critical"), (60, "High"), (30, "Medium"), (0, "Low")]

FACTOR_LABELS = {
    "amount": "Unusual amount",
    "delay": "Payment delay",
    "anomaly": "Anomaly model score",
    "duplicate": "Possible duplicate",
    "vendor_history": "Vendor payment history",
    "frequency": "Unusual invoice frequency",
}


def _ramp(values, start, end) -> np.ndarray:
    """Linear 0-to-1 ramp: 0 at/below `start`, 1 at/above `end`.
    Converts a raw measurement into a 0-1 'how worrying is it' value."""
    v = np.asarray(values, dtype=float)
    return np.clip((v - start) / (end - start), 0.0, 1.0)


def risk_level(score: float) -> str:
    """Map a 0-100 score to Low / Medium / High / Critical."""
    for lower, label in RISK_LEVELS:
        if score >= lower:
            return label
    return "Low"


def compute_components(features: pd.DataFrame, anomaly: pd.DataFrame,
                       duplicate_score=None) -> pd.DataFrame:
    """
    Compute each risk factor as a 0-1 value.

    Inputs
      features        : output of features.build_features()
      anomaly         : output of anomaly_detection.score_invoices()
      duplicate_score : optional 0-1 array (Phase 5). Defaults to all zeros.
    Output: DataFrame with one 0-1 column per factor in WEIGHTS.
    """
    dup = np.zeros(len(features)) if duplicate_score is None else np.asarray(duplicate_score, float)
    return pd.DataFrame({
        # 1.5x typical is fine; 4x or more is maximum concern
        "amount": _ramp(features["amount_ratio"], 1.5, 4.0),
        # on time = 0; 30+ days late = maximum concern
        "delay": _ramp(features["effective_delay"], 0, 30),
        "anomaly": anomaly["anomaly_score"].values,
        "duplicate": dup,
        # vendor whose average delay is above 3 days; 20+ = maximum
        "vendor_history": _ramp(features["vendor_avg_delay"], 3, 20),
        # vendor billing 1.5x the typical vendor's volume; 4x = maximum
        "frequency": _ramp(features["vendor_volume_ratio"], 1.5, 4.0),
    }, index=features.index)


def _reason_text(factor: str, row: pd.Series) -> str:
    """Plain-English sentence for one factor of one invoice."""
    if factor == "amount":
        return f"Invoice amount is {row['amount_ratio']:.1f}x the vendor's typical amount."
    if factor == "delay":
        if row["payment_status"] in ("Overdue", "Pending") and pd.isna(row["payment_date"]):
            return f"Invoice is unpaid and {row['effective_delay']:.0f} days past its due date."
        return f"Payment was {row['effective_delay']:.0f} days after the due date."
    if factor == "anomaly":
        return "The anomaly model rates this invoice as unusual compared with the rest."
    if factor == "duplicate":
        other = row.get("duplicate_of", "") if hasattr(row, "get") else ""
        return f"Possible duplicate of {other}." if other else "Possible duplicate of another invoice."
    if factor == "vendor_history":
        return f"This vendor pays late on average ({row['vendor_avg_delay']:.0f} days)."
    if factor == "frequency":
        return f"This vendor sends {row['vendor_volume_ratio']:.1f}x the typical number of invoices."
    return factor


def score_risk(features: pd.DataFrame, anomaly: pd.DataFrame,
               duplicate_score=None) -> pd.DataFrame:
    """
    Compute risk score, level and explanation for every invoice.

    Output columns: invoice_id, risk_score (0-100), risk_level, reasons
    where `reasons` is a list of dicts:
        {"factor", "label", "points", "text"}
    `points` = how many of the 100 points this factor contributed, which is
    what the UI draws as a bar chart. Only factors that add >= 3 points are
    listed, so explanations stay short and meaningful.
    """
    comps = compute_components(features, anomaly, duplicate_score)
    points = comps.mul(pd.Series(WEIGHTS)) * 100.0
    total = points.sum(axis=1).round(1)

    reasons_col = []
    for i in features.index:
        row = features.loc[i]
        items = []
        for factor in WEIGHTS:
            p = float(points.loc[i, factor])
            if p >= 3.0:
                items.append({
                    "factor": factor,
                    "label": FACTOR_LABELS[factor],
                    "points": round(p, 1),
                    "text": _reason_text(factor, row),
                })
        items.sort(key=lambda d: d["points"], reverse=True)
        reasons_col.append(items)

    return pd.DataFrame({
        "invoice_id": features["invoice_id"].values,
        "risk_score": total.values,
        "risk_level": [risk_level(s) for s in total.values],
        "reasons": reasons_col,
    })
