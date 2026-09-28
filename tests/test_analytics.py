"""Analytics + insights, and the whole ML pipeline on the demo data."""

import json
from unittest import mock

import numpy as np
import pandas as pd

import src.ml_models as mm
from src.analytics import aging_summary, concentration, monthly_summary, unpaid, vendor_summary
from src.dashboard_data import assemble
from src.features import build_features
from src.insights import generate_insights
from tests.helpers import demo_df


def _run_pipeline():
    """Run the REAL pipeline on the demo CSV, with only the database swapped out."""
    raw = demo_df()
    saved = {}
    with mock.patch.object(mm, "init_db", lambda: None), \
         mock.patch.object(mm, "load_invoices_df", lambda engine: raw.copy()), \
         mock.patch.object(mm, "save_models", lambda bundle: None), \
         mock.patch.object(mm, "_write_results", lambda a, r: saved.update(a=a, r=r)):
        summary = mm.run_full_analysis()
    a, r = saved["a"], saved["r"]
    risk = r.assign(reasons=r["reasons"].map(json.dumps))[["invoice_id", "risk_score", "risk_level", "reasons"]]
    df = assemble(build_features(raw), risk, a[["invoice_id", "anomaly_score", "is_anomaly"]])
    return summary, df


_CACHE = {}
def _pipeline():
    if "x" not in _CACHE:
        _CACHE["x"] = _run_pipeline()
    return _CACHE["x"]


def test_pipeline_scores_every_invoice():
    summary, df = _pipeline()
    assert summary["invoices_analysed"] == len(df) == 1167
    assert df["analysed"].all()
    assert df["risk_score"].between(0, 100).all()


def test_anomaly_rate_is_close_to_the_3_percent_setting():
    summary, _ = _pipeline()
    assert 30 <= summary["anomalies_found"] <= 40


def test_extreme_amounts_are_caught():
    _, df = _pipeline()
    tiny = df[df["amount"] < 10]
    huge = df[df["amount"] > 300_000]
    assert len(tiny) and len(huge)
    assert tiny["is_anomaly"].all() and huge["is_anomaly"].all()


def test_normal_big_vendor_is_not_falsely_flagged():
    _, df = _pipeline()
    v112 = df[(df["vendor_id"] == "V112") & (df["amount_ratio"] < 2)]
    assert not v112["is_anomaly"].any()


def test_reasons_survive_the_json_round_trip():
    _, df = _pipeline()
    top = df.sort_values("risk_score", ascending=False).iloc[0]
    assert isinstance(top["reasons"], list) and top["reasons"]


def test_vendor_summary_covers_every_vendor_and_shares_add_to_one():
    _, df = _pipeline()
    vs = vendor_summary(df)
    assert len(vs) == df["vendor_id"].nunique() == 35
    assert np.isclose(vs["share_of_spend"].sum(), 1.0)


def test_aging_buckets_add_up_to_unpaid_invoices():
    _, df = _pipeline()
    assert aging_summary(df)["invoices"].sum() == len(unpaid(df))


def test_monthly_and_concentration_are_sane():
    _, df = _pipeline()
    assert np.isclose(monthly_summary(df)["value"].sum(), df["amount"].sum())
    assert 0 < concentration(df, 5) <= 1


def test_insights_are_generated_with_valid_severities():
    _, df = _pipeline()
    items = generate_insights(df)
    assert len(items) >= 4
    assert all(sev in ("high", "medium", "info") and head and detail for sev, head, detail in items)
