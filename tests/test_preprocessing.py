"""CSV validation: bad rows are dropped and counted, never crash."""

import io

import pandas as pd
import pytest

from src.preprocessing import REQUIRED_COLUMNS, ValidationError, validate_and_clean
from tests.helpers import demo_df

HEADER = "invoice_id,vendor_id,vendor_name,invoice_date,due_date,payment_date,amount,tax,discount,payment_status,payment_delay,category\n"


def _csv(*rows):
    return pd.read_csv(io.StringIO(HEADER + "\n".join(rows) + "\n"))


def test_clean_demo_file_has_no_problems():
    raw = pd.read_csv("data/sample_invoices.csv")
    clean, report = validate_and_clean(raw)
    assert report["total_rows"] == 1167
    assert report["imported"] == 1167
    assert report["warnings"] == report["duplicates"] == report["invalid_rows"] == 0


def test_messy_file_is_cleaned_and_counted():
    raw = _csv(
        "A1,V1,One,2026-01-01,2026-01-31,2026-01-30,100,5,0,Paid,-1,Utilities",       # good
        "A1,V1,One,2026-01-02,2026-02-01,2026-02-01,120,5,0,Paid,0,Utilities",        # repeated ID
        "A2,V1,One,not-a-date,2026-02-01,,120,5,0,Pending,,Utilities",                # bad date
        "A3,V1,One,2026-01-05,2026-02-05,,-50,5,0,Pending,,Utilities",                # negative amount
        ",V1,One,2026-01-05,2026-02-05,,50,5,0,Pending,,Utilities",                   # missing ID
        "A4,V1,One,2026-01-06,2026-02-06,,80,5,200,Pending,,Utilities",               # discount > amount (warning)
        "A5,V1,One,2026-01-07,2026-02-07,,90,5,0,Paid,,Utilities",                    # Paid without date (warning)
    )
    clean, report = validate_and_clean(raw)
    assert report["invalid_rows"] == 3
    assert report["duplicates"] == 1
    assert report["warnings"] == 2
    assert len(clean) == 3


def test_missing_required_column_gives_clear_error():
    raw = pd.read_csv("data/sample_invoices.csv").drop(columns=["amount"])
    with pytest.raises(ValidationError) as err:
        validate_and_clean(raw)
    assert "amount" in str(err.value)


def test_empty_file_gives_clear_error():
    with pytest.raises(ValidationError):
        validate_and_clean(pd.DataFrame(columns=REQUIRED_COLUMNS))
