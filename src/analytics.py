"""
src/analytics.py
------------------
Pure-pandas summaries used by the Vendors and Analytics pages.
No Streamlit and no database code, so each function can be tested alone.
Input is the DataFrame produced by dashboard_data.load_results().
"""

from __future__ import annotations

import pandas as pd

AGING_BUCKETS = ["Not yet due", "1-30 days", "31-60 days", "61-90 days", "Over 90 days"]


def unpaid(df: pd.DataFrame) -> pd.DataFrame:
    """Invoices with no recorded payment."""
    return df[df["payment_date"].isna() & df["payment_status"].isin(["Pending", "Overdue"])]


def vendor_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per vendor: volume, spend, lateness, and risk figures."""
    g = df.groupby(["vendor_id", "vendor_name"])
    out = g.agg(
        category=("category", lambda s: s.mode().iat[0] if len(s.mode()) else ""),
        invoices=("invoice_id", "count"),
        total_spend=("amount", "sum"),
        avg_amount=("amount", "mean"),
        avg_days_late=("effective_delay", "mean"),
        overdue=("payment_status", lambda s: int((s == "Overdue").sum())),
        anomalies=("is_anomaly", "sum"),
        possible_duplicates=("duplicate_score", lambda s: int((s > 0).sum())),
        avg_risk=("risk_score", "mean"),
        max_risk=("risk_score", "max"),
    ).reset_index()
    out["anomalies"] = out["anomalies"].astype(int)
    out["share_of_spend"] = out["total_spend"] / out["total_spend"].sum()

    def watch(r):
        flags = []
        if r["avg_days_late"] > 10:
            flags.append("pays late")
        if r["anomalies"] >= 3:
            flags.append("many anomalies")
        if r["possible_duplicates"] >= 4:
            flags.append("many duplicates")
        if r["share_of_spend"] > 0.08:
            flags.append("large share of spend")
        return ", ".join(flags)

    out["watch"] = out.apply(watch, axis=1)
    return out.sort_values("total_spend", ascending=False).reset_index(drop=True)


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Invoice count, value, and month-over-month change per month."""
    m = df.groupby("month").agg(invoices=("invoice_id", "count"), value=("amount", "sum")).reset_index()
    m = m.sort_values("month").reset_index(drop=True)
    m["change_pct"] = m["value"].pct_change() * 100
    return m


def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    c = df.groupby("category").agg(invoices=("invoice_id", "count"), value=("amount", "sum"),
                                   avg_risk=("risk_score", "mean")).reset_index()
    return c.sort_values("value", ascending=False).reset_index(drop=True)


def aging_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Unpaid invoices grouped by how long they are past due (as of the
    latest date in the data)."""
    u = unpaid(df)
    d = u["effective_delay"]
    bucket = pd.cut(d, bins=[-1, 0, 30, 60, 90, 10**6], labels=AGING_BUCKETS)
    out = (u.assign(bucket=bucket).groupby("bucket", observed=False)
             .agg(invoices=("invoice_id", "count"), value=("amount", "sum")).reset_index())
    return out


def concentration(df: pd.DataFrame, top_n: int = 5) -> float:
    """Share of total spend that goes to the top_n vendors (0-1)."""
    by_vendor = df.groupby("vendor_id")["amount"].sum().sort_values(ascending=False)
    total = by_vendor.sum()
    return float(by_vendor.head(top_n).sum() / total) if total else 0.0
