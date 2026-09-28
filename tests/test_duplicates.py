"""Duplicate detection rules."""

from src.duplicate_detection import detect_duplicates
from tests.helpers import demo_df, make_invoices


def _detect(rows):
    return detect_duplicates(make_invoices(rows))


def test_same_vendor_amount_and_date_is_exact_match_for_both():
    d = _detect([{"invoice_date": "2026-03-01", "amount": 500.00},
                 {"invoice_date": "2026-03-01", "amount": 500.00}])
    assert list(d["duplicate_score"]) == [1.0, 1.0]
    assert "INV-001" in d["duplicate_of"].iloc[0] and "INV-000" in d["duplicate_of"].iloc[1]


def test_same_amount_within_a_week_is_strong():
    d = _detect([{"invoice_date": "2026-03-01", "amount": 500.00},
                 {"invoice_date": "2026-03-06", "amount": 500.00}])
    assert list(d["duplicate_score"]) == [0.8, 0.8]


def test_different_vendors_never_match():
    d = _detect([{"invoice_date": "2026-03-01", "amount": 500.00},
                 {"invoice_date": "2026-03-01", "amount": 500.00, "vendor_id": "V2"}])
    assert (d["duplicate_score"] == 0).all()


def test_same_amount_a_month_apart_is_not_a_duplicate():
    d = _detect([{"invoice_date": "2026-03-01", "amount": 500.00},
                 {"invoice_date": "2026-04-01", "amount": 500.00}])
    assert (d["duplicate_score"] == 0).all()


def test_all_planted_demo_duplicates_are_found():
    df = demo_df()
    d = detect_duplicates(df)
    planted = df.groupby(["vendor_id", "amount", "invoice_date"])["invoice_id"].transform("count") > 1
    assert planted.sum() == 34                       # 17 planted pairs
    assert (d.loc[planted, "duplicate_score"] > 0).all()
