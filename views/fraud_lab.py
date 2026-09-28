"""views/fraud_lab.py -- attack your own data and see what InvoiceIQ catches. Nothing is saved to your invoices."""

import html

import streamlit as st

from src.database import engine
from src.features import load_invoices_df
from src.fraud_lab import (ALARMS, ATTACKS, DEFAULT_LIMIT, caught_by, run_lab, summarise, why_caught,
                           why_missed)
from src.ml_models import load_anomaly_bundle
from src.ui import finding_card, kpi_row, money, note, page_header, panel_mark

LEVELS = {"Medium and above (score 30+)": 30.0, "High and above (score 60+)": 60.0}
WEAK_BELOW = 0.6      # attacks caught less often than this get a "what to build" suggestion

_CSS = """
<style>
.lab-wall {position: relative; background: linear-gradient(180deg, #0f1729, #0c1424); border: 1px solid var(--iq-line, #22304d);
  border-radius: 14px; padding: 18px 20px 12px; overflow: hidden;}
.lab-row {display: grid; grid-template-columns: minmax(150px, 210px) 1fr 74px; gap: 16px; align-items: center; padding: 9px 0;
  border-bottom: 1px solid rgba(51, 71, 102, .35);}
.lab-row:last-child {border-bottom: 0;}
.lab-name b {display: block; color: #f1f5f9; font-family: 'Sora', 'DM Sans', sans-serif; font-size: .95rem; font-weight: 600;}
.lab-name span {color: #94a3b8; font-size: .78rem; line-height: 1.3; display: block;}
.lab-tiles {display: grid; grid-template-columns: repeat(var(--cols), minmax(0, 1fr)); gap: 3px;}
.lab-tiles i {height: 24px; border-radius: 4px; background: #22c55e; box-shadow: 0 0 10px -2px rgba(34, 197, 94, .7);
  animation: lab-flip .45s cubic-bezier(.2, .8, .2, 1) backwards var(--d);}
.lab-tiles i.miss {background: #ef4444; box-shadow: 0 0 12px -1px rgba(239, 68, 68, .85);}
.lab-tiles i.luck {background: #f59e0b; box-shadow: 0 0 10px -2px rgba(245, 158, 11, .7);}
@keyframes lab-flip {from {background: #22304d; box-shadow: none; transform: scale(.35) rotate(-20deg); opacity: .25;}}
.lab-rate {text-align: right; font-family: 'Sora', sans-serif; color: #f1f5f9; font-weight: 700; font-size: 1.25rem; line-height: 1;
  font-variant-numeric: tabular-nums;}
.lab-rate small {display: block; margin-top: 4px; color: #94a3b8; font-family: 'DM Sans', sans-serif; font-weight: 500; font-size: .74rem;}
.lab-scan {position: absolute; top: 0; bottom: 0; left: calc(100% - 96px); width: 3px; opacity: 0; pointer-events: none;
  background: linear-gradient(180deg, transparent, #38bdf8, transparent); box-shadow: 0 0 22px 6px rgba(56, 189, 248, .55);
  animation: lab-scan 2.7s cubic-bezier(.4, 0, .2, 1) backwards;}
@keyframes lab-scan {from {left: 224px; opacity: 1;} 92% {opacity: 1;} to {left: calc(100% - 96px); opacity: 0;}}
.lab-legend {display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 12px 0 2px; color: #94a3b8; font-size: .82rem;}
.lab-legend i {display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 6px; vertical-align: -1px;}
@media (max-width: 720px) {.lab-row {grid-template-columns: 1fr; gap: 6px;} .lab-rate {text-align: left;} .lab-scan {display: none;}}
</style>
"""


def _tile_title(row, verdict: str) -> str:
    return html.escape(f"{row['invoice_id']}  {row['vendor_name']}  {money(row['amount'])}  score {row['risk_score']:.0f}  {verdict}")


def _wall(result, summary) -> str:
    """One row per attack; each fake invoice is a tile that flips green (caught) or red (missed) as the scan passes."""
    inv, al = result.invoices, summary["alarms"]
    rows = []
    for p in summary["per_attack"]:
        sub = inv[inv["attack"] == p["key"]]
        n = len(sub)
        cols = min(n, 40)
        tiles = []
        for i, (idx, r) in enumerate(sub.iterrows()):
            a = al.loc[idx]
            if not a["caught"]:
                cls, verdict = "miss", "MISSED"
            elif a["chance"]:
                cls, verdict = "luck", "caught by chance (duplicate check)"
            else:
                cls, verdict = "", "caught by " + caught_by(a)
            delay = (i % cols) / cols * 2.4 + (i // cols) * 0.12
            tiles.append(f'<i class="{cls}" style="--d:{delay:.2f}s" title="{_tile_title(r, verdict)}"></i>')
        rows.append(
            f'<div class="lab-row"><div class="lab-name"><b>{html.escape(p["title"])}</b><span>{html.escape(p["blurb"])}</span></div>'
            f'<div class="lab-tiles" style="--cols:{cols}">{"".join(tiles)}</div>'
            f'<div class="lab-rate">{p["caught"]}/{p["total"]}<small>{p["caught"] / p["total"]:.0%} caught</small></div></div>')
    legend = ('<div class="lab-legend"><span><i style="background:#22c55e"></i>Caught</span>'
              '<span><i style="background:#f59e0b"></i>Caught by chance: only the duplicate check fired, by coincidence of similar amounts</span>'
              '<span><i style="background:#ef4444"></i>Missed</span></div>')
    return f'<div class="lab-wall"><div class="lab-scan"></div>{"".join(rows)}</div>{legend}'


def _default_state() -> None:
    st.session_state.setdefault("lab_result", None)


def render(df) -> None:
    page_header("Fraud Lab", "Attack your own data and see what InvoiceIQ catches. Nothing is saved to your invoices.")
    st.markdown(_CSS, unsafe_allow_html=True)
    _default_state()

    with st.container(border=True):
        panel_mark()
        picked = st.multiselect("Attacks to run", list(ATTACKS), default=list(ATTACKS), key="lab_picked",
                                format_func=lambda k: f"{ATTACKS[k]['title']}: {ATTACKS[k]['blurb']}")
        c1, c2, c3 = st.columns([1, 1, 1])
        per = c1.slider("Fake invoices per attack", 6, 60, 30, step=6, key="lab_n",
                        help="Split, creeping-price and shell-vendor attacks are made in sets of 3 or 6 invoices.")
        limit = c2.number_input("Your approval limit ($)", min_value=100.0, value=float(DEFAULT_LIMIT), step=500.0,
                                key="lab_limit", help="Used by the 'Split under the limit' attack.")
        with c3:
            st.write("")
            run = st.button("Run attack", type="primary", key="lab_run", use_container_width=True)
        with st.expander("Advanced"):
            st.number_input("Random seed", min_value=0, value=42, step=1, key="lab_seed",
                            help="The same seed gives the exact same fake invoices, so a result can be repeated.")

    if run:
        if not picked:
            st.warning("Pick at least one attack to run.")
        else:
            try:
                with st.spinner("Hiding fake invoices among your real ones and running every detector..."):
                    base = load_invoices_df(engine)
                    st.session_state["lab_result"] = run_lab(
                        base, {k: per for k in picked}, bundle=load_anomaly_bundle(),
                        seed=int(st.session_state["lab_seed"]), approval_limit=float(limit))
            except Exception as exc:
                st.error(f"The attack could not run ({exc}).")

    result = st.session_state["lab_result"]
    if result is None:
        st.write("")
        note("Press Run attack. InvoiceIQ mixes fake invoices into a copy of your data in memory, "
             "runs the same detectors it uses on real invoices, and shows what it caught and what slipped through.")
        return

    st.write("")
    f1, f2 = st.columns([1, 1])
    level = f1.selectbox("Risk score counts as an alarm from", list(LEVELS), key="lab_level")
    use = f2.multiselect("Alarms that count as 'caught'", list(ALARMS), default=list(ALARMS), key="lab_use",
                         format_func=lambda k: ALARMS[k],
                         help="An invoice is caught when at least one of these alarms goes off for it.")
    if not use:
        st.warning("Pick at least one alarm.")
        return
    s = summarise(result, LEVELS[level], tuple(use))
    missed_n = s["total"] - s["caught"]

    kpi_row([
        ("Fake invoices caught", f"{s['caught']}", f"of {s['total']} hidden in your data" + (f", {s['chance']} only by chance" if s["chance"] else ""),
         "#22c55e" if s["rate"] >= .7 else "#f59e0b" if s["rate"] >= .4 else "#ef4444"),
        ("Detection rate", f"{s['rate']:.0%}", "of the attack invoices raised an alarm", "#38bdf8"),
        ("Slipped through", f"{missed_n}", "no alarm at all", "#ef4444" if missed_n else "#22c55e"),
        ("False alarms on real data", f"{s['false_alarm_rate']:.0%}", f"{s['false_alarm_n']} of {s['n_real']:,} real invoices, same alarms",
         "#f59e0b", "The same alarms, counted on your real invoices. A detector that flags everything would score 100% above."),
    ])
    st.write("")
    st.markdown(_wall(result, s), unsafe_allow_html=True)
    st.caption("Hover a tile to see the invoice. Fake invoices are unpaid and not yet due, so lateness cannot help the detector: "
               "only the trick itself is tested. The anomaly model is the one trained on your clean data and has never seen these attacks.")

    # ---- what to build next ----
    weak = [p for p in s["per_attack"] if p["caught"] / p["total"] < WEAK_BELOW]
    st.subheader("What to build next")
    if not weak:
        st.success("Every attack was caught more than 60% of the time. Try more invoices per attack, or a new seed.")
    else:
        for i, p in enumerate(sorted(weak, key=lambda q: q["caught"] / q["total"])):
            st.markdown(finding_card("high" if p["caught"] / p["total"] < .3 else "medium",
                                     f"{p['title']}: caught {p['caught']} of {p['total']} ({p['caught'] / p['total']:.0%})",
                                     p["fix"], i), unsafe_allow_html=True)

    # ---- the invoices ----
    inv = result.invoices.copy()
    al = s["alarms"]
    inv["caught"] = al["caught"].values
    inv["title"] = inv["attack"].map(lambda k: ATTACKS[k]["title"])
    inv["invoice_date"] = inv["invoice_date"].dt.date
    st.subheader("Every fake invoice")
    show = st.radio("Show", ["Slipped through", "Caught", "All"], horizontal=True, key="lab_show")
    view = inv if show == "All" else inv[~inv["caught"]] if show == "Slipped through" else inv[inv["caught"]]
    if view.empty:
        st.info("Nothing to show here.")
    else:
        view = view.copy()
        view["verdict"] = [
            why_missed(r) if not r["caught"] else f"{caught_by(al.loc[i])}. {why_caught(r, al.loc[i])}"
            for i, r in view.iterrows()]
        table = view[["title", "invoice_id", "vendor_name", "invoice_date", "amount", "risk_score", "note", "verdict"]]
        st.dataframe(table, hide_index=True, column_config={
            "title": "Attack", "invoice_id": "Invoice", "vendor_name": "Vendor", "invoice_date": "Date",
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "risk_score": st.column_config.NumberColumn("Risk score", format="%.1f"),
            "note": "How it was faked", "verdict": "Result and reason"})
        st.download_button("Download this table (CSV)", table.to_csv(index=False).encode("utf-8"),
                           file_name="fraud_lab_results.csv", mime="text/csv", key="lab_dl")

    note(f"How to read this: the attacks are simple tricks written into InvoiceIQ (seed {result.seed}), so a rate here shows how the "
         "detector handles these tricks and nothing more. Real fraud may look different. Run again with a new seed to check the "
         "numbers are stable.")
