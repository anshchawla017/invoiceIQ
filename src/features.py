"""
src/features.py
-----------------
Feature engineering: turns raw invoice rows into numbers that describe
how UNUSUAL each invoice is compared with (a) the vendor's own history and
(b) the rest of the dataset.

Why feature engineering matters
  A raw amount of $9,000 means nothing on its own. It is normal for a
  vendor who usually bills $9,000 and very suspicious for one who usually
  bills $2,000. So instead of feeding raw columns to the model, we build
  RELATIVE features such as "amount / vendor's typical amount".

Input : a DataFrame with one row per invoice (see load_invoices_df)
Output: the same rows plus engineered columns (listed in FEATURE_COLUMNS)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text

# The exact columns the Isolation Forest is trained on.
FEATURE_COLUMNS = [
    # WHY THESE FIVE (chosen by comparing feature sets, see README "Feature
    # selection"): each one measures how unusual THIS invoice is relative to
    # normal. Vendor-level constants (vendor average delay, vendor volume) and
    # tax/discount rates were tested and REMOVED from the model: they made
    # whole vendors look abnormal or added noise. Vendor-level behaviour is
    # still scored, transparently, by the risk engine (src/risk_engine.py).
    #
    # Money is on a LOG scale because raw dollars are extremely skewed: one
    # $400k invoice stretches the range so far that a $3 invoice goes unnoticed.
    "log_amount",            # log(1 + amount): catches $3 and $500k alike
    "log_amount_ratio",      # log(amount / vendor typical). 0 = typical for the vendor
    "effective_delay",       # days paid after due date (or days overdue if unpaid)
    "delay_deviation",       # this invoice's delay minus the vendor's usual delay
    "vendor_burst_7d",       # invoices from this vendor within +/-7 days of this one
]

_LOAD_SQL = text("""
    SELECT i.invoice_id, i.vendor_id, v.vendor_name, i.invoice_date, i.due_date,
           i.amount, i.tax, i.discount, i.payment_status, i.category,
           p.payment_date, p.payment_delay
    FROM invoices i
    JOIN vendors v ON v.vendor_id = i.vendor_id
    LEFT JOIN payments p ON p.invoice_id = i.invoice_id
""")


def load_invoices_df(engine) -> pd.DataFrame:
    """Read invoices + vendor name + payment info from SQL in one JOIN query."""
    df = pd.read_sql(_LOAD_SQL, engine, parse_dates=["invoice_date", "due_date", "payment_date"])
    return df


def _burst_counts(dates: pd.Series, window_days: int = 7) -> np.ndarray:
    """For each date, count how many dates in the same series fall within
    +/- window_days (including itself). Uses sorted arrays + binary search,
    which is much faster than comparing every pair."""
    days = dates.values.astype("datetime64[D]").astype("int64")
    order = np.argsort(days)
    sorted_days = days[order]
    left = np.searchsorted(sorted_days, days - window_days, side="left")
    right = np.searchsorted(sorted_days, days + window_days, side="right")
    return (right - left).astype(int)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add engineered feature columns to the invoice DataFrame.

    Returns a NEW DataFrame (the input is not modified). Raises ValueError
    if the input is empty so the UI can show a friendly message.
    """
    if df is None or len(df) == 0:
        raise ValueError("No invoices available to analyse. Load data first.")

    out = df.copy()

    # "As of" date = latest date seen in the data. Used to measure how long
    # an unpaid invoice has been overdue.
    as_of = max(out["invoice_date"].max(), out["payment_date"].max()
                if out["payment_date"].notna().any() else out["invoice_date"].max())

    # effective_delay: for paid invoices use the recorded delay; for unpaid
    # invoices use days past due as of today (never negative).
    days_past_due = (as_of - out["due_date"]).dt.days.clip(lower=0)
    out["effective_delay"] = out["payment_delay"].where(out["payment_delay"].notna(), days_past_due)
    out["effective_delay"] = out["effective_delay"].astype(float)

    # ---- vendor history (median is used because it is not distorted by
    # the very outliers we are trying to find; a mean would be) ----
    grp = out.groupby("vendor_id")
    out["vendor_median_amount"] = grp["amount"].transform("median")
    out["vendor_avg_delay"] = grp["effective_delay"].transform("mean")
    out["vendor_invoice_count"] = grp["invoice_id"].transform("count")

    out["amount_ratio"] = out["amount"] / out["vendor_median_amount"].replace(0, np.nan)
    out["amount_ratio"] = out["amount_ratio"].fillna(1.0)
    out["delay_deviation"] = out["effective_delay"] - out["vendor_avg_delay"]

    # ---- scale-free money features (see FEATURE_COLUMNS comment) ----
    out["log_amount"] = np.log1p(out["amount"])
    out["log_amount_ratio"] = np.log(out["amount_ratio"].clip(lower=1e-6))

    # ---- frequency features ----
    median_count = out.drop_duplicates("vendor_id")["vendor_invoice_count"].median()
    out["vendor_volume_ratio"] = out["vendor_invoice_count"] / max(median_count, 1)

    out["vendor_burst_7d"] = 0
    for _, idx in out.groupby("vendor_id").groups.items():
        out.loc[idx, "vendor_burst_7d"] = _burst_counts(out.loc[idx, "invoice_date"])

    out[FEATURE_COLUMNS] = out[FEATURE_COLUMNS].fillna(0.0)   # safety net; models cannot take NaN
    return out
