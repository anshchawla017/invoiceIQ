"""views/data_import.py -- upload a CSV/Excel file, validate it, import it, analyse it."""

import pandas as pd
import streamlit as st

from src.dashboard_data import MIN_INVOICES_FOR_ANALYSIS, count_invoices
from src.ml_models import run_full_analysis
from src.preprocessing import (OPTIONAL_COLUMNS, REQUIRED_COLUMNS, ValidationError,
                               import_dataframe, validate_and_clean)
from src.ui import kpi_row, page_header, pipeline


def _read(uploaded) -> pd.DataFrame:
    if uploaded.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded)
    return pd.read_csv(uploaded)


def render() -> None:
    page_header("Data Import", "Bring in your own invoices. Your file is checked first, and nothing is saved until you confirm.")
    steps = [
        ("Upload a file", "A CSV or Excel file with one row per invoice."),
        ("Check the report", "See how many rows are fine, and which have problems."),
        ("Import and score", "Good rows are saved and every invoice is scored."),
    ]
    stage = st.container()
    st.write("")

    with st.expander("Required file format"):
        st.write("**Required columns:** " + ", ".join(f"`{c}`" for c in REQUIRED_COLUMNS))
        st.write("**Optional columns:** " + ", ".join(f"`{c}`" for c in OPTIONAL_COLUMNS))
        template = ",".join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS) + "\n"
        st.download_button("Download an empty template (CSV)", template, file_name="invoiceiq_template.csv",
                           mime="text/csv")

    uploaded = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls"])
    if uploaded is None:
        with stage:
            pipeline(steps, 0)
        return

    try:
        raw = _read(uploaded)
    except Exception as exc:
        with stage:
            pipeline(steps, 1)
        st.error(f"This file could not be read ({exc}). Please upload a .csv or .xlsx file.")
        return

    try:
        clean, report = validate_and_clean(raw)
    except ValidationError as exc:
        with stage:
            pipeline(steps, 1)
        st.error(str(exc))
        return

    with stage:
        pipeline(steps, 2)
    kpi_row([
        ("Rows in file", f"{report['total_rows']:,}"),
        ("Ready to import", f"{report['imported']:,}", "rows that passed all checks", "#22c55e"),
        ("Warnings", f"{report['warnings']:,}", "kept, but worth checking", "#f59e0b"),
        ("Repeated invoice IDs", f"{report['duplicates']:,}", "skipped", "#f97316"),
        ("Unusable rows", f"{report['invalid_rows']:,}", "skipped", "#ef4444"),
    ])
    st.write("")
    for msg in report["warning_details"]:
        st.warning(msg)
    for msg in report["invalid_details"]:
        st.error(msg)

    st.caption("Preview of the first rows that will be imported")
    preview = clean.head(10).copy()
    for col in ("invoice_date", "due_date", "payment_date"):
        preview[col] = preview[col].dt.date
    st.dataframe(preview, hide_index=True)

    if report["imported"] == 0:
        st.error("None of the rows in this file can be imported. Check the messages above and the required format.")
        return

    existing = count_invoices()
    mode = "Add to existing data"
    if existing:
        mode = st.radio(f"The database already holds {existing:,} invoices.",
                        ["Add to existing data", "Replace existing data"])
        st.caption("Adding skips any invoice_id that is already stored.")

    if st.button("Import and score invoices", type="primary"):
        try:
            result = import_dataframe(clean, replace_existing=(mode == "Replace existing data"))
        except Exception as exc:
            st.error(str(exc))
            return
        total = count_invoices()
        if total < MIN_INVOICES_FOR_ANALYSIS:
            st.session_state["flash"] = (
                f"Imported {result['inserted']} invoices, but the database has only {total}. "
                f"Risk analysis needs at least {MIN_INVOICES_FOR_ANALYSIS} invoices, so it was skipped.")
            st.rerun()
        try:
            with st.spinner("Saving invoices, then training the models and scoring them..."):
                summary = run_full_analysis()
        except Exception as exc:
            st.session_state["flash_error"] = f"Imported {result['inserted']} invoices, but analysis failed: {exc}"
            st.rerun()
        st.session_state["flash"] = (
            f"Imported {result['inserted']} new invoices ({result['skipped_existing']} already existed). "
            f"{summary['invoices_analysed']:,} analysed, {summary['anomalies_found']} flagged, {summary['possible_duplicates']} possible duplicates.")
        st.rerun()
