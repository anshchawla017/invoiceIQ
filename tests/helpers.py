"""Small builders shared by the tests."""

import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_CSV = os.path.join(ROOT, "data", "sample_invoices.csv")


def demo_df() -> pd.DataFrame:
    """The demo CSV with dates parsed, as load_invoices_df would return it."""
    return pd.read_csv(DEMO_CSV, parse_dates=["invoice_date", "due_date", "payment_date"])


def make_invoices(rows: list[dict]) -> pd.DataFrame:
    """Build a tiny invoice table; unspecified columns get sensible defaults."""
    base = {"vendor_id": "V1", "vendor_name": "Vendor One", "tax": 0.0, "discount": 0.0,
            "payment_status": "Paid", "category": "Utilities", "payment_delay": 0.0}
    out = []
    for i, r in enumerate(rows):
        row = {**base, "invoice_id": f"INV-{i:03d}", **r}
        row["invoice_date"] = pd.Timestamp(row["invoice_date"])
        row["due_date"] = pd.Timestamp(row.get("due_date", row["invoice_date"] + pd.Timedelta(days=30)))
        row["payment_date"] = pd.Timestamp(row["payment_date"]) if row.get("payment_date") else pd.NaT
        out.append(row)
    return pd.DataFrame(out)
