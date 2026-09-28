"""Feature engineering: relative-to-vendor features behave as designed."""

import numpy as np
import pandas as pd
import pytest

from src.features import FEATURE_COLUMNS, build_features
from tests.helpers import make_invoices


def _rows():
    rows = [{"invoice_date": f"2026-01-{d:02d}", "amount": 1000.0, "payment_delay": 0.0} for d in range(1, 10)]
    rows.append({"invoice_date": "2026-01-20", "amount": 8000.0, "payment_delay": 25.0})
    return make_invoices(rows)


def test_empty_input_raises_friendly_error():
    with pytest.raises(ValueError):
        build_features(make_invoices([]).iloc[0:0])


def test_amount_ratio_is_relative_to_vendor_median():
    f = build_features(_rows())
    assert f["vendor_median_amount"].iloc[0] == 1000.0     # median ignores the outlier
    assert f["amount_ratio"].iloc[-1] == 8.0
    assert np.isclose(f["log_amount_ratio"].iloc[-1], np.log(8.0))


def test_no_missing_values_in_model_features():
    f = build_features(_rows())
    assert not f[FEATURE_COLUMNS].isna().any().any()


def test_unpaid_invoice_uses_days_past_due():
    rows = _rows()
    rows.loc[0, ["payment_status", "payment_delay", "payment_date"]] = ["Overdue", np.nan, pd.NaT]
    f = build_features(rows)
    assert f["effective_delay"].iloc[0] >= 0


def test_input_is_not_modified():
    rows = _rows()
    before = list(rows.columns)
    build_features(rows)
    assert list(rows.columns) == before