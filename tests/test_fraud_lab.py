"""Tests for the Fraud Lab engine (src/fraud_lab.py). Pure pandas: no database, no Streamlit."""

import pandas as pd
import pytest

from src import fraud_lab as fl
from src.anomaly_detection import train_isolation_forest
from src.features import build_features
from tests.helpers import demo_df

ALL = {k: 12 for k in fl.ATTACKS}


@pytest.fixture(scope="module")
def base():
    return demo_df()


@pytest.fixture(scope="module")
def bundle(base):
    return train_isolation_forest(build_features(base))


@pytest.fixture(scope="module")
def result(base, bundle):
    return fl.run_lab(base, ALL, bundle, seed=1)


def test_same_seed_gives_identical_attacks(base):
    a = fl.generate_attacks(base, ALL, seed=5)
    b = fl.generate_attacks(base, ALL, seed=5)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(fl.generate_attacks(base, ALL, seed=6))


def test_counts_follow_set_sizes(base):
    a = fl.generate_attacks(base, {"spike": 7, "split": 7, "creep": 13, "shell": 6}, seed=2)
    counts = a["attack"].value_counts().to_dict()
    assert counts == {"spike": 7, "split": 6, "creep": 12, "shell": 6}   # whole sets only


def test_attack_invoices_are_unpaid_and_never_overdue(base, result):
    inv = result.invoices
    assert (inv["payment_status"] == "Pending").all()
    assert (inv["effective_delay"] == 0).all()          # lateness must not help detection
    assert inv["invoice_id"].str.startswith("ATK-").all()
    assert not inv["invoice_id"].isin(base["invoice_id"]).any()


def test_real_invoices_are_kept_and_counted(base, result):
    assert result.n_base == len(base) == len(result.real)
    assert len(result.invoices) == len(result.invoices["invoice_id"].unique())


def test_copy_paste_duplicates_are_caught(result):
    s = fl.summarise(result)
    row = next(p for p in s["per_attack"] if p["key"] == "copy")
    assert row["caught"] == row["total"]


def test_a_spike_scores_higher_than_normal_invoices(result):
    spike = result.invoices[result.invoices["attack"] == "spike"]
    assert spike["risk_score"].mean() > result.real["risk_score"].mean() + 10


def test_shell_vendors_are_new_and_round(result):
    shell = result.invoices[result.invoices["attack"] == "shell"]
    assert shell["vendor_id"].str.startswith("V-ATK-").all()
    assert ((shell["amount"] % 100) == 0).all()


def test_split_invoices_sit_just_under_the_limit(base, bundle):
    r = fl.run_lab(base, {"split": 9}, bundle, seed=3, approval_limit=8000)
    amounts = r.invoices["amount"]
    assert amounts.between(8000 * 0.90, 8000 * 0.99).all()


def test_summary_numbers_add_up(result):
    s = fl.summarise(result)
    assert s["total"] == sum(p["total"] for p in s["per_attack"]) == len(result.invoices)
    assert s["caught"] == sum(p["caught"] for p in s["per_attack"])
    assert 0 <= s["rate"] <= 1 and 0 <= s["false_alarm_rate"] <= 1
    assert s["chance"] <= s["caught"]


def test_stricter_alarms_never_catch_more(result):
    loose = fl.summarise(result, 30.0, ("risk", "anomaly", "duplicate"))
    strict = fl.summarise(result, 60.0, ("risk",))
    assert strict["caught"] <= loose["caught"]
    assert strict["false_alarm_rate"] <= loose["false_alarm_rate"]


def test_reasons_are_written_for_every_verdict(result):
    s = fl.summarise(result)
    al = s["alarms"]
    for i, row in result.invoices.iterrows():
        text = fl.why_caught(row, al.loc[i]) if al.loc[i, "caught"] else fl.why_missed(row)
        assert isinstance(text, str) and len(text) > 10


def test_errors_are_friendly(base, bundle):
    with pytest.raises(ValueError, match="Pick at least one"):
        fl.run_lab(base, {}, bundle)
    with pytest.raises(ValueError, match="no invoices"):
        fl.run_lab(base.iloc[0:0], ALL, bundle)


def test_runs_without_a_saved_model(base):
    r = fl.run_lab(base, {"spike": 6}, bundle=None, seed=1)
    assert len(r.invoices) == 6
