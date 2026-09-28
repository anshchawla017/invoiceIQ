"""
generate_sample_data.py
------------------------
Generates data/sample_invoices.csv — the bundled "Load Demo Dataset" for
InvoiceIQ. This is intentionally NOT pure randomness: it plants specific,
explainable patterns that later phases (anomaly detection, risk scoring,
duplicate detection) are built to catch. Knowing what was planted here is
what lets you explain, in a viva, *why* the model flags what it flags.

Patterns planted on purpose:
  1. Normal invoices                -> the majority baseline
  2. Unusually large invoices        -> amount = 4-8x that vendor's own average
  3. Delayed payments                -> 5 "chronically late" vendors
  4. Duplicate-like invoices         -> same vendor+amount+date, new invoice_id
  5. Unusual vendor frequency        -> 2 vendors invoice far more often than peers
  6. Unusual absolute amounts        -> a few invoices at extreme absolute values
  7. A handful of "obvious" anomalies combining several red flags at once

Run:
    python src/generate_sample_data.py
"""

import numpy as np
import pandas as pd

RANDOM_SEED = 42
N_BASE_INVOICES = 1150          # before duplicates/extra bursts are added
TODAY = pd.Timestamp("2026-06-30")  # fixed reference date for reproducibility

CATEGORIES = [
    "Office Supplies", "IT Services", "Consulting", "Logistics",
    "Raw Materials", "Utilities", "Marketing", "Maintenance",
    "Software Licenses", "Travel",
]

VENDOR_NAME_PARTS = [
    "Nimbus", "Vertex", "Orion", "Summit", "Falcon", "Granite", "Beacon",
    "Cascade", "Pioneer", "Harbor", "Meridian", "Anchor", "Lumen", "Atlas",
    "Crescent", "Ironclad", "Silverline", "Redwood", "Horizon", "Pinnacle",
    "Stratos", "Fieldstone", "Copperleaf", "Northgate", "Bluewave",
    "Cobalt", "Everline", "Highland", "Junction", "Kestrel", "Larkspur",
    "Marlin", "Novapoint", "Ostrich", "Paragon",
]
VENDOR_SUFFIXES = ["Inc.", "LLC", "Ltd.", "Group", "Solutions", "Partners"]


def make_vendors(rng, n_vendors=35):
    """Each vendor gets a stable 'personality': typical invoice size,
    category, payment terms, and (for a few) chronic lateness or unusual
    frequency. This is what makes 'vendor history' comparisons meaningful
    later — an invoice is only unusual RELATIVE to that vendor's own norm."""
    vendor_ids = [f"V{100+i}" for i in range(n_vendors)]
    names = [
        f"{VENDOR_NAME_PARTS[i]} {rng.choice(VENDOR_SUFFIXES)}"
        for i in range(n_vendors)
    ]
    avg_amount = rng.lognormal(mean=8.2, sigma=0.6, size=n_vendors).round(2)  # ~ 1.5k-15k
    category = rng.choice(CATEGORIES, n_vendors)
    payment_terms = rng.choice([15, 30, 45], n_vendors, p=[0.25, 0.55, 0.20])

    # 5 vendors are chronically late payers; 2 vendors invoice unusually often
    chronically_late = set(rng.choice(n_vendors, size=5, replace=False))
    high_frequency = set(rng.choice(
        [i for i in range(n_vendors) if i not in chronically_late],
        size=2, replace=False,
    ))

    vendors = pd.DataFrame({
        "vendor_id": vendor_ids,
        "vendor_name": names,
        "avg_amount": avg_amount,
        "category": category,
        "payment_terms": payment_terms,
        "is_chronically_late": [i in chronically_late for i in range(n_vendors)],
        "is_high_frequency": [i in high_frequency for i in range(n_vendors)],
    })
    return vendors


def assign_invoice_counts(rng, vendors: pd.DataFrame, total: int) -> np.ndarray:
    """Most vendors get a normal share of invoices; the 2 'high frequency'
    vendors get 3-5x their fair share — this is the 'unusual vendor
    frequency' pattern the anomaly/analytics modules should surface."""
    n = len(vendors)
    weights = np.ones(n)
    weights[vendors["is_high_frequency"].values] = 4.0
    weights = weights / weights.sum()
    counts = rng.multinomial(total, weights)
    return counts


def generate_dataset(seed=RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    vendors = make_vendors(rng)
    counts = assign_invoice_counts(rng, vendors, N_BASE_INVOICES)

    rows = []
    invoice_counter = 1

    for v_idx, vendor in vendors.iterrows():
        n_for_vendor = counts[v_idx]
        if n_for_vendor == 0:
            continue

        # Spread this vendor's invoices across the past ~12 months
        days_back = rng.integers(0, 365, n_for_vendor)
        invoice_dates = TODAY - pd.to_timedelta(days_back, unit="D")

        for inv_date in invoice_dates:
            invoice_id = f"INV-{invoice_counter:05d}"
            invoice_counter += 1

            # ---- amount: normal, with occasional planted outliers ----
            amount = float(rng.lognormal(mean=np.log(vendor["avg_amount"]), sigma=0.25))
            is_large_outlier = rng.random() < 0.02       # ~2% unusually large
            if is_large_outlier:
                amount *= rng.uniform(4, 8)
            is_extreme_absolute = rng.random() < 0.004   # rare extreme absolute values
            if is_extreme_absolute:
                amount = rng.choice([rng.uniform(1, 5), rng.uniform(300000, 600000)])
            amount = round(max(amount, 1.0), 2)

            tax_rate = rng.choice([0.05, 0.08, 0.12, 0.18])
            tax = round(amount * tax_rate, 2)
            discount = round(amount * rng.uniform(0, 0.05) if rng.random() < 0.3 else 0.0, 2)

            due_date = inv_date + pd.Timedelta(days=int(vendor["payment_terms"]))

            # ---- payment behavior ----
            if vendor["is_chronically_late"]:
                delay_days = int(rng.normal(loc=18, scale=8))
            else:
                delay_days = int(rng.normal(loc=1, scale=5))

            if due_date > TODAY and rng.random() < 0.4:
                # not yet due, and not paid early -> still pending
                payment_status = "Pending"
                payment_date = pd.NaT
                payment_delay = np.nan
            elif due_date <= TODAY and (due_date + pd.Timedelta(days=max(delay_days, 0))) > TODAY:
                # would have paid late, but that late date is still in the future -> overdue now
                payment_status = "Overdue"
                payment_date = pd.NaT
                payment_delay = np.nan
            else:
                payment_status = "Paid"
                payment_date = due_date + pd.Timedelta(days=delay_days)
                if payment_date > TODAY:
                    payment_date = TODAY
                payment_delay = int((payment_date - due_date).days)

            rows.append({
                "invoice_id": invoice_id,
                "vendor_id": vendor["vendor_id"],
                "vendor_name": vendor["vendor_name"],
                "invoice_date": inv_date.date().isoformat(),
                "due_date": due_date.date().isoformat(),
                "payment_date": payment_date.date().isoformat() if pd.notna(payment_date) else "",
                "amount": amount,
                "tax": tax,
                "discount": discount,
                "payment_status": payment_status,
                "payment_delay": payment_delay,
                "category": vendor["category"],
            })

    df = pd.DataFrame(rows)

    # ---- plant duplicate-like invoices (~1.5%) ----
    n_dupes = int(len(df) * 0.015)
    dupe_source_idx = rng.choice(df.index, size=n_dupes, replace=False)
    dupes = df.loc[dupe_source_idx].copy()
    dupes["invoice_id"] = [f"INV-{invoice_counter + i:05d}" for i in range(n_dupes)]
    invoice_counter += n_dupes
    df = pd.concat([df, dupes], ignore_index=True)

    # ---- plant a handful of "obvious" combined anomalies (~8 invoices) ----
    obvious_idx = rng.choice(df.index, size=8, replace=False)
    df.loc[obvious_idx, "amount"] = df.loc[obvious_idx, "amount"] * rng.uniform(5, 9, size=8)
    df.loc[obvious_idx, "payment_status"] = "Overdue"
    df.loc[obvious_idx, "payment_date"] = ""
    df.loc[obvious_idx, "payment_delay"] = np.nan
    df["amount"] = df["amount"].round(2)
    df["tax"] = df["tax"].round(2)

    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)  # shuffle
    return df, vendors


if __name__ == "__main__":
    df, vendors = generate_dataset()
    df.to_csv("data/sample_invoices.csv", index=False)

    print(f"Generated {len(df)} invoices across {vendors['vendor_id'].nunique()} vendors")
    print(f"-> data/sample_invoices.csv")
    print("\nPayment status breakdown:")
    print(df["payment_status"].value_counts())
    print(f"\nHigh-frequency vendors: {vendors[vendors['is_high_frequency']]['vendor_id'].tolist()}")
    print(f"Chronically late vendors: {vendors[vendors['is_chronically_late']]['vendor_id'].tolist()}")
    print(f"\nAmount stats:\n{df['amount'].describe()}")
