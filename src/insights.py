"""
src/insights.py
-----------------
Turns the numbers into a short list of plain-English findings for the
'Executive insights' panel. Every sentence is built from a real calculation
on the loaded data by fixed rules. There is no text generation model here.

Each insight is a tuple:  (severity, headline, detail)
    severity is one of "high", "medium", "info".
"""

from __future__ import annotations

import pandas as pd

from src.analytics import concentration, unpaid, vendor_summary


def _money(x: float) -> str:
    return f"${x:,.0f}"


def generate_insights(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    if df.empty:
        return out

    # 1. overdue exposure
    overdue = df[df["payment_status"] == "Overdue"]
    if len(overdue):
        worst = overdue.sort_values("amount", ascending=False).iloc[0]
        out.append(("high", f"{len(overdue)} overdue invoices worth {_money(overdue['amount'].sum())}",
                    f"The largest is {worst['invoice_id']} from {worst['vendor_name']} "
                    f"({_money(worst['amount'])}, {worst['effective_delay']:.0f} days past due)."))

    # 2. high / critical risk
    hi = df[df["risk_level"].isin(["High", "Critical"])]
    if len(hi):
        out.append(("high", f"{len(hi)} invoices scored High or Critical risk",
                    f"Together they are worth {_money(hi['amount'].sum())}. Review them first on the Risk Analysis page."))

    # 3. possible duplicates
    dup = df[df["duplicate_score"] > 0]
    strong = df[df["duplicate_score"] >= 0.8]
    if len(dup):
        out.append(("medium", f"{len(dup)} invoices look like possible duplicates",
                    f"{len(strong)} are strong matches (same vendor and amount, at most a week apart), worth "
                    f"{_money(strong['amount'].sum())}. Because both invoices in a pair are marked, "
                    f"the amount actually at risk of double payment is about half of that."))

    # 4. anomalies
    an = df[df["is_anomaly"]]
    if len(an):
        out.append(("medium", f"The model flagged {len(an)} unusual invoices ({len(an) / len(df):.1%})",
                    f"Their total value is {_money(an['amount'].sum())}. "
                    f"{int((an['risk_level'] == 'Low').sum())} of them still have a Low risk score "
                    f"(unusual, but paid on time and not repeated)."))

    # 5. late-paying vendors
    vs = vendor_summary(df)
    late = vs[vs["avg_days_late"] > 10].sort_values("avg_days_late", ascending=False)
    if len(late):
        names = ", ".join(late["vendor_name"].head(3))
        out.append(("medium", f"{len(late)} vendors are paid more than 10 days late on average",
                    f"Worst: {names}."))

    # 6. spend concentration
    share = concentration(df, 5)
    top = vs.iloc[0]
    out.append(("info", f"Top 5 vendors take {share:.0%} of total spend",
                f"The largest is {top['vendor_name']} at {_money(top['total_spend'])} "
                f"({top['share_of_spend']:.0%} of spend, {int(top['invoices'])} invoices)."))

    # 7. unpaid but not yet overdue
    pend = unpaid(df)
    pend = pend[pend["payment_status"] == "Pending"]
    if len(pend):
        out.append(("info", f"{len(pend)} invoices are pending payment",
                    f"Worth {_money(pend['amount'].sum())} in total."))
    return out
