"""
app.py -- InvoiceIQ entry point.   Run with:   streamlit run app.py

Sidebar navigation + first-run welcome screen. Each page lives in views/ and
exposes a render(df) function. (The folder is called views/, not pages/,
because Streamlit auto-builds its own menu from a folder named pages/.)
"""

import streamlit as st

st.set_page_config(page_title="InvoiceIQ", page_icon="🧾", layout="wide")

from src.intro import show_intro  # noqa: E402

show_intro()  # ~7 second opening screen, once per browser session; drawn before the heavy imports below

from src.dashboard_data import count_invoices, load_demo_and_analyse, load_results  # noqa: E402
from src.database import init_db  # noqa: E402
from src.ui import brand_block, inject_css, flash, status_pill, step_cards, welcome_hero  # noqa: E402
from views import (analytics, anomaly_explorer, dashboard, data_import,  # noqa: E402
                   duplicates, help_page, invoices, model_center, risk_analysis, vendors)

init_db()
inject_css(st.session_state.get("iq_animate", True))

# label shown in the sidebar -> page module
PAGES = {
    "📊  Dashboard": dashboard,
    "🧾  Invoices": invoices,
    "🎯  Risk Analysis": risk_analysis,
    "🔍  Anomaly Explorer": anomaly_explorer,
    "👥  Duplicates": duplicates,
    "🏢  Vendors": vendors,
    "📈  Analytics": analytics,
    "🧠  Model Center": model_center,
    "📥  Data Import": data_import,
    "❓  Help": help_page,
}
# pages that work without any data loaded
NO_DATA_OK = (data_import, help_page)


def _load_demo() -> None:
    try:
        with st.spinner("Loading 1,167 demo invoices and training the models. This takes a few seconds."):
            summary = load_demo_and_analyse()
        st.session_state["flash"] = (
            f"Demo data is ready: {summary['invoices_analysed']:,} invoices checked, "
            f"{summary['anomalies_found']} unusual ones flagged, "
            f"{summary['possible_duplicates']} possible duplicates found."
        )
    except Exception as exc:  # show a friendly message, never a traceback
        st.session_state["flash_error"] = (
            f"The demo data could not be loaded ({exc}). Check that data/sample_invoices.csv exists, "
            "then try again.")
    st.rerun()


n_invoices = count_invoices()

with st.sidebar:
    st.markdown(brand_block(), unsafe_allow_html=True)
    page_name = st.radio("Go to", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.toggle("Animations", value=True, key="iq_animate", help="Turn off if the app feels slow or you prefer a still page.")
    st.markdown(status_pill(n_invoices), unsafe_allow_html=True)
    st.write("")
    if n_invoices:
        if st.button("Reload demo data", key="sidebar_demo"):
            _load_demo()
        st.caption("Reloading replaces everything with the demo dataset.")
    else:
        if st.button("Load demo data", key="sidebar_demo", type="primary"):
            _load_demo()

if "flash" in st.session_state:
    flash(st.session_state.pop("flash"))
if "flash_error" in st.session_state:
    st.error(st.session_state.pop("flash_error"))

page = PAGES[page_name]

# ---- first run: nothing in the database yet ----
if n_invoices == 0 and page not in NO_DATA_OK:
    welcome_hero("Welcome to InvoiceIQ",
                 "InvoiceIQ checks every invoice for warning signs, such as an amount far above normal, a late "
                 "payment, or a possible double entry, and explains each one in plain English.")
    step_cards([
        ("Add invoices", "Load the demo dataset, or upload your own CSV or Excel file on the Data Import page."),
        ("We score them", "Each invoice gets a risk score from 0 to 100, with the reasons behind it."),
        ("Review what matters", "Start with the highest scores. Everything is explained, nothing is a black box."),
    ])
    st.write("")
    if st.button("Load demo data", key="onboard_demo", type="primary"):
        _load_demo()
    st.caption("The demo has 1,167 made-up invoices from 35 vendors, so no real data is needed to explore.")
    st.stop()

if page is data_import:
    data_import.render()
elif page is help_page:
    help_page.render()
else:
    try:
        df = load_results()
    except Exception as exc:
        st.error(f"The database could not be read: {exc}")
        st.stop()
    page.render(df)
