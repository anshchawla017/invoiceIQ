"""
src/duplicate_detection.py
----------------------------
Finds invoices that look like the same bill entered twice.

What it does : compares every pair of invoices FROM THE SAME VENDOR.
Why needed   : paying a duplicate invoice is one of the most common and
               costly accounting errors. It also feeds the 15-point
               'possible duplicate' factor in the risk score.
Input        : DataFrame with invoice_id, vendor_id, amount, invoice_date.
Output       : DataFrame (same index) with
                 duplicate_score  0-1  (0 = no match)
                 duplicate_of     text, e.g. "INV-00012, INV-00340"

Rules (a pair is only compared if it is the same vendor, different ID):
    1.0  same amount to the cent AND same invoice date
    0.8  same amount (within 0.1%) AND dates within 7 days
    0.5  amounts within 1% AND dates within 3 days
An invoice takes the HIGHEST score over all its partners. BOTH invoices of a
matching pair are marked, because we cannot know which one is the original.

Limitation: this is a rule-based match on amount and date. It does not read
invoice numbers or line items, so a genuinely repeating bill with the same
amount inside a week (for example two identical deliveries) can be flagged
by mistake. It marks candidates for a human to check.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _pair_score(amount_diff_abs, amount_diff_rel, days) -> float:
    if amount_diff_abs <= 0.005 and days == 0:
        return 1.0
    if amount_diff_rel <= 0.001 and days <= 7:
        return 0.8
    if amount_diff_rel <= 0.01 and days <= 3:
        return 0.5
    return 0.0


def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    score = np.zeros(n)
    partners: list[list[tuple[float, str]]] = [[] for _ in range(n)]
    pos = {idx: i for i, idx in enumerate(df.index)}

    for _, group in df.groupby("vendor_id"):
        if len(group) < 2:
            continue
        idxs = [pos[i] for i in group.index]
        amounts = group["amount"].to_numpy(float)
        days = group["invoice_date"].values.astype("datetime64[D]").astype("int64")
        ids = group["invoice_id"].to_numpy()
        for a in range(len(group)):
            for b in range(a + 1, len(group)):
                diff = abs(amounts[a] - amounts[b])
                rel = diff / max(amounts[a], amounts[b], 1e-9)
                s = _pair_score(diff, rel, abs(int(days[a] - days[b])))
                if s > 0:
                    for me, other in ((a, b), (b, a)):
                        i = idxs[me]
                        score[i] = max(score[i], s)
                        partners[i].append((s, str(ids[other])))

    of = [", ".join(p for _, p in sorted(pl, reverse=True)[:3]) for pl in partners]
    return pd.DataFrame({"duplicate_score": score, "duplicate_of": of}, index=df.index)
