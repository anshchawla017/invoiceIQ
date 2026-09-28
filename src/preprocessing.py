"""
src/preprocessing.py
----------------------
Turns a raw uploaded CSV into (a) a validated report the user can read,
and (b) clean rows actually written into the database.

Two separate concerns, on purpose:
  1. validate_and_clean(df)  -- pure pandas, no database. Easy to unit test.
  2. import_dataframe(df)    -- takes the CLEAN df and writes it to SQL.

This split means Phase 4's upload workflow can show the validation report
to the user (Imported / Warnings / Duplicates / Invalid rows) BEFORE
anything touches the database, and the pipeline never crashes the app on
bad input -- bad rows are dropped and counted, not thrown as exceptions.
"""

from __future__ import annotations

import pandas as pd

from src.database import Invoice, Payment, Vendor, get_session, init_db

REQUIRED_COLUMNS = [
    "invoice_id", "vendor_id", "vendor_name", "invoice_date", "due_date",
    "amount", "tax", "discount", "payment_status", "category",
]
OPTIONAL_COLUMNS = ["payment_date", "payment_delay"]


class ValidationError(Exception):
    """Raised only for unrecoverable problems (e.g. missing required
    columns entirely) -- never for row-level issues, which are cleaned
    and counted instead of raised."""


def validate_and_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Validate and clean a raw invoice DataFrame.

    Returns:
        (clean_df, report) where report is a dict like:
        {
            "total_rows": 947,
            "imported": 933,
            "warnings": 12,
            "duplicates": 4,
            "invalid_rows": 10,
            "warning_details": [...],
            "invalid_details": [...],
        }
    """
    if df is None or len(df) == 0:
        raise ValidationError("The uploaded file has no rows.")

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValidationError(
            f"Missing required column(s): {', '.join(missing_cols)}. "
            f"Expected at least: {', '.join(REQUIRED_COLUMNS)}."
        )

    df = df.copy()
    total_rows = len(df)
    warning_details = []
    invalid_details = []

    # Ensure optional columns exist so downstream code never KeyErrors
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    # ---- parse dates (bad/unparseable dates become NaT, not a crash) ----
    for col in ["invoice_date", "due_date", "payment_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # ---- parse numerics ----
    for col in ["amount", "tax", "discount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ---- INVALID rows: dropped, counted, never crash the app ----
    invalid_mask = (
        df["invoice_id"].isna() | (df["invoice_id"].astype(str).str.strip() == "")
        | df["vendor_id"].isna()
        | df["invoice_date"].isna()
        | df["due_date"].isna()
        | df["amount"].isna()
        | (df["amount"] <= 0)
    )
    if invalid_mask.any():
        invalid_details.append(f"{int(invalid_mask.sum())} rows missing required fields, "
                                f"with an invalid date, or amount <= 0")
    invalid_rows = int(invalid_mask.sum())
    df = df[~invalid_mask].copy()

    # ---- DUPLICATES: exact same invoice_id appearing more than once ----
    dup_mask = df.duplicated(subset=["invoice_id"], keep="first")
    duplicates = int(dup_mask.sum())
    if duplicates:
        invalid_details.append(f"{duplicates} rows had an invoice_id already seen earlier "
                                f"in the file (kept the first occurrence)")
    df = df[~dup_mask].copy()

    # ---- WARNINGS: kept, but flagged as inconsistent ----
    warnings_count = 0

    # e.g. marked Paid but has no payment_date
    inconsistent_paid = (df["payment_status"].str.lower() == "paid") & df["payment_date"].isna()
    if inconsistent_paid.any():
        n = int(inconsistent_paid.sum())
        warning_details.append(f"{n} invoices marked 'Paid' have no payment_date")
        warnings_count += n

    # e.g. discount larger than the invoice amount itself
    bad_discount = df["discount"].fillna(0) > df["amount"]
    if bad_discount.any():
        n = int(bad_discount.sum())
        warning_details.append(f"{n} invoices have a discount larger than the invoice amount")
        warnings_count += n

    # fill missing tax/discount with 0 rather than dropping the row
    df["tax"] = df["tax"].fillna(0.0)
    df["discount"] = df["discount"].fillna(0.0)
    df["category"] = df["category"].fillna("Uncategorized")
    df["vendor_name"] = df["vendor_name"].fillna(df["vendor_id"])

    report = {
        "total_rows": total_rows,
        "imported": len(df),
        "warnings": warnings_count,
        "duplicates": duplicates,
        "invalid_rows": invalid_rows,
        "warning_details": warning_details,
        "invalid_details": invalid_details,
    }
    return df.reset_index(drop=True), report


def import_dataframe(df: pd.DataFrame, replace_existing: bool = False) -> dict:
    """
    Write a CLEAN dataframe (already passed through validate_and_clean)
    into the database: upserts vendors, then invoices, then payments.

    Wrapped in a transaction -- if anything fails partway through, the
    whole import is rolled back rather than leaving a half-written state.
    """
    init_db()
    session = get_session()
    inserted, skipped = 0, 0

    try:
        if replace_existing:
            session.query(Payment).delete()
            session.query(Invoice).delete()
            session.query(Vendor).delete()
            session.commit()

        # ---- upsert vendors (one row per unique vendor_id) ----
        existing_vendor_ids = {v.vendor_id for v in session.query(Vendor.vendor_id).all()}
        vendor_rows = df.drop_duplicates(subset=["vendor_id"])[["vendor_id", "vendor_name", "category"]]
        for _, row in vendor_rows.iterrows():
            if row["vendor_id"] not in existing_vendor_ids:
                session.add(Vendor(
                    vendor_id=row["vendor_id"],
                    vendor_name=row["vendor_name"],
                    category=row["category"],
                ))
                existing_vendor_ids.add(row["vendor_id"])
        session.commit()

        # ---- insert invoices + payments ----
        existing_invoice_ids = {i.invoice_id for i in session.query(Invoice.invoice_id).all()}
        for _, row in df.iterrows():
            if row["invoice_id"] in existing_invoice_ids:
                skipped += 1
                continue

            invoice = Invoice(
                invoice_id=row["invoice_id"],
                vendor_id=row["vendor_id"],
                invoice_date=row["invoice_date"].date(),
                due_date=row["due_date"].date(),
                amount=float(row["amount"]),
                tax=float(row["tax"]),
                discount=float(row["discount"]),
                payment_status=str(row["payment_status"]),
                category=str(row["category"]),
            )
            session.add(invoice)

            payment_date = row.get("payment_date")
            payment_delay = row.get("payment_delay")
            has_payment_date = pd.notna(payment_date)
            has_payment_delay = pd.notna(payment_delay)
            if has_payment_date or has_payment_delay:
                session.add(Payment(
                    invoice_id=row["invoice_id"],
                    payment_date=payment_date.date() if has_payment_date else None,
                    payment_delay=int(payment_delay) if has_payment_delay else None,
                ))
            inserted += 1

        session.commit()
        return {"inserted": inserted, "skipped_existing": skipped}

    except Exception as exc:
        session.rollback()
        raise RuntimeError(f"Database import failed and was rolled back: {exc}") from exc
    finally:
        session.close()


def load_and_import_csv(csv_path: str, replace_existing: bool = False) -> dict:
    """Convenience wrapper: read a CSV file straight through the full
    validate -> clean -> import pipeline. Used by the demo-dataset loader
    and by tests."""
    raw_df = pd.read_csv(csv_path)
    clean_df, report = validate_and_clean(raw_df)
    import_result = import_dataframe(clean_df, replace_existing=replace_existing)
    report.update(import_result)
    return report
