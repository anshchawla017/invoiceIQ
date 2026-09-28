"""views/help_page.py -- plain-language guide to the terms used in the app."""

import streamlit as st

from src.risk_engine import FACTOR_LABELS, WEIGHTS
from src.ui import LEVEL_DOT, note, page_header


def render() -> None:
    page_header("Help", "What the words in InvoiceIQ mean, and how to use each page.")

    st.subheader("The three checks")
    st.markdown(
        "**Anomaly.** An invoice that looks unusual compared with the rest, judged by a machine-learning "
        "model called Isolation Forest. It looks at the size of the amount compared with that vendor's "
        "usual invoices, how late the payment is, and how many invoices the vendor sent around the same time. "
        "Unusual does not mean wrong.\n\n"
        "**Possible duplicate.** Two invoices from the same vendor with the same (or almost the same) amount "
        "and a very close date. Both are marked, because the app cannot know which is the original.\n\n"
        "**Risk score.** A number from 0 to 100 that adds up six warning signs. The higher it is, the more "
        "the invoice deserves a human look. It is a checklist score, not a fraud verdict."
    )

    st.subheader("Risk levels")
    st.markdown(
        f"{LEVEL_DOT['Low']} **Low** (0 to 29) nothing much stands out.  \n"
        f"{LEVEL_DOT['Medium']} **Medium** (30 to 59) worth a quick look.  \n"
        f"{LEVEL_DOT['High']} **High** (60 to 79) review before paying.  \n"
        f"{LEVEL_DOT['Critical']} **Critical** (80 to 100) several serious warning signs at once."
    )

    st.subheader("How the score is built")
    st.table({"Warning sign": [FACTOR_LABELS[k] for k in WEIGHTS],
              "Most points it can add": [round(v * 100) for v in WEIGHTS.values()]})

    st.subheader("Where to start")
    st.markdown(
        "1. **Dashboard** for the big picture and the key findings.\n"
        "2. **Risk Analysis**: pick an invoice and read *Why was this flagged?*\n"
        "3. **Duplicates** to check possible double entries.\n"
        "4. **Vendors** to see who is paid late or sends unusual invoices.\n"
        "5. **Data Import** to check your own file."
    )
    note("InvoiceIQ points at invoices worth reviewing. It cannot prove fraud or error. A person should "
         "always confirm before rejecting or paying anything.")
