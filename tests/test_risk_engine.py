"""Risk score: weights, levels, bounds and explanations."""

import numpy as np
import pandas as pd

from src.risk_engine import RISK_LEVELS, WEIGHTS, risk_level, score_risk
from tests.helpers import make_invoices
from src.features import build_features


def test_weights_add_up_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_level_boundaries():
    assert risk_level(0) == "Low" and risk_level(29.9) == "Low"
    assert risk_level(30) == "Medium" and risk_level(59.9) == "Medium"
    assert risk_level(60) == "High" and risk_level(79.9) == "High"
    assert risk_level(80) == "Critical" and risk_level(100) == "Critical"
    assert [name for _, name in RISK_LEVELS] == ["Critical", "High", "Medium", "Low"]


def _scored(duplicate=None):
    rows = [{"invoice_date": f"2026-01-{d:02d}", "amount": 1000.0} for d in range(1, 11)]
    rows.append({"invoice_date": "2026-02-01", "amount": 9000.0, "payment_delay": 40.0})
    f = build_features(make_invoices(rows))
    anomaly = pd.DataFrame({"invoice_id": f["invoice_id"], "anomaly_score": np.linspace(0, 1, len(f)),
                            "is_anomaly": False})
    return f, score_risk(f, anomaly, duplicate_score=duplicate)


def test_scores_stay_between_0_and_100():
    _, r = _scored()
    assert r["risk_score"].between(0, 100).all()


def test_big_late_invoice_scores_higher_than_normal_one():
    _, r = _scored()
    assert r["risk_score"].iloc[-1] > r["risk_score"].iloc[0]


def test_duplicate_factor_adds_exactly_its_weight():
    f, base = _scored()
    dup = np.zeros(len(f)); dup[0] = 1.0
    _, with_dup = _scored(duplicate=dup)
    assert np.isclose(with_dup["risk_score"].iloc[0] - base["risk_score"].iloc[0], 15.0, atol=0.11)


def test_reasons_have_points_text_and_are_sorted():
    _, r = _scored()
    reasons = r["reasons"].iloc[-1]
    assert reasons, "the big late invoice must have reasons"
    pts = [x["points"] for x in reasons]
    assert pts == sorted(pts, reverse=True)
    assert all(x["text"] and x["points"] >= 3 for x in reasons)
