# InvoiceIQ: AI-Powered Invoice Intelligence & Risk Detection

InvoiceIQ reads invoice data, stores it in a relational database, and checks
every invoice for warning signs: an amount far above the vendor's norm, a late
or overdue payment, a possible double entry, or a vendor that behaves oddly.
Each invoice gets a **0-100 risk score with the reasons written out in plain
English**, and everything is shown in a multi-page Streamlit dashboard.

It flags invoices that deserve a human look. It does **not** prove fraud.

## Quick start

```bash
# 1. from the project root (the folder that contains app.py)
python -m venv venv
venv\Scripts\activate            # Windows      (Mac/Linux: source venv/bin/activate)
python -m pip install -r requirements.txt

# 2. run the dashboard
python -m streamlit run app.py
```
Open the sidebar and click **Load demo data**. That loads 1,167 synthetic
invoices, trains the models and scores everything in a few seconds. To use your
own file, go to **Data Import**.

Optional command-line route (same result as the button):
```bash
python -m src.init_demo_db       # create data/database.db and load the demo CSV
python -m src.ml_models          # train models, score invoices, save models/*.pkl
python -m pytest                 # run the test suite (from the project root)
```
Expected output of `python -m src.ml_models` on the demo data: 1,167 invoices,
35 anomalies, 46 possible duplicates, risk levels Low 1114 / Medium 47 /
High 6 / Critical 0.

## What you can do in the app

| Page | What it is for |
|---|---|
| Dashboard | Key numbers, "what needs attention", charts, the 10 riskiest invoices |
| Invoices | Search, filter and export every invoice |
| Risk Analysis | Pick an invoice and see **why** it got its score (gauge, points per factor, sentences) |
| Anomaly Explorer | What the model found unusual, and what made each invoice stand out |
| Duplicates | Possible double entries, labelled Exact / Strong / Weak |
| Vendors | Spend, lateness and risk per vendor, with a drill-down |
| Analytics | Monthly trend, spend by category, unpaid-invoice aging, key findings |
| Fraud Lab | Hides fake invoices (6 attack types) among your real ones, runs the real detectors and shows what was caught, what slipped through and why |
| Model Center | Real model settings and statistics, and why there is no "accuracy" |
| Data Import | Upload CSV/Excel, see a validation report, import, score |
| Help | Plain-language explanation of every term |

## How it works

```
CSV / Excel --> validate & clean --> SQLite (5 tables)
                                          |
                          features.py (5 features per invoice)
                                          |
        anomaly_detection.py (Isolation Forest)    duplicate_detection.py (rules)
                         \                              /
                          risk_engine.py (6-factor weighted score)
                                          |
             results saved to SQL + models saved to models/*.pkl
                                          |
                        dashboard_data.py --> views/*.py (Streamlit)
```

### Database (SQLAlchemy over SQLite)
`vendors`, `invoices`, `payments`, `risk_predictions`, `anomaly_results`, linked
by foreign keys. A real database (rather than one DataFrame) means data survives
restarts, relationships are enforced, and imports are transactional: a failed
import rolls back completely, and re-importing a file skips invoice IDs that are
already stored.

### Validation (`src/preprocessing.py`)
Bad rows never crash the app. Unusable rows (no ID, bad date, amount <= 0) and
repeated invoice IDs are dropped and counted; inconsistencies (a "Paid" invoice
with no payment date, a discount larger than the amount) are kept but reported
as warnings. Missing required columns give a one-line error, not a traceback.

### Features (`src/features.py`)
Five numbers, each measuring how unusual an invoice is *relative to normal*:
`log_amount`, `log_amount_ratio` (vs the vendor's median invoice),
`effective_delay`, `delay_deviation` (vs the vendor's usual delay) and
`vendor_burst_7d` (invoices from the vendor within +/-7 days). Vendor "typical"
values use the **median**, because a mean is dragged around by the very outliers
being hunted.

### Anomaly detection (`src/anomaly_detection.py`)
**Isolation Forest**, 200 trees, `contamination = 0.03`, `random_state = 42`.
The idea: unusual points are easy to isolate with random splits, so they end up
with short paths in the trees. It is unsupervised, so it needs no labelled fraud.
The 3% is an **assumption** about how many invoices are unusual, not something
learned. Each flagged invoice gets a plain-English reason built from the features.

**Feature selection (an honest account).** The first version used raw dollars,
tax, discount and vendor-level averages. Checked against the patterns planted in
the demo data, it missed a $3.70 invoice (one $406K invoice stretched the raw
range) and flagged 12 normal invoices from vendor V112, whose usual invoice is
about $14K. Four feature sets were compared on the same data:

| Feature set | Big (>=4x) caught /25 | Extreme /2 | Obvious /8 | V112 false flags |
|---|---|---|---|---|
| A: all 10 (logs + rates + vendor constants) | 15 | 1 | 8 | 3 |
| B: A minus tax/discount rates | 20 | 1 | 8 | 0 |
| **C: chosen (the 5 above)** | **21** | **2** | **8** | **0** |
| D: C minus burst | 18 | 2 | 8 | 0 |

### Duplicate detection (`src/duplicate_detection.py`)
Compares invoices **from the same vendor only**. Exact = same amount to the cent
and same date (1.0). Strong = amount within 0.1% and within 7 days (0.8). Weak =
amount within 1% and within 3 days (0.5). Both invoices of a pair are marked.

### Risk score (`src/risk_engine.py`)
Score = 100 x the weighted sum of six factors, each between 0 and 1:

| Factor | Weight |
|---|---|
| Unusual amount (vs vendor's typical) | 25 |
| Payment delay | 20 |
| Anomaly model score | 20 |
| Possible duplicate | 15 |
| Vendor payment history | 10 |
| Unusual invoice frequency | 10 |

Levels: 0-29 Low, 30-59 Medium, 60-79 High, 80-100 Critical. Every factor that
contributes 3+ points is stored with its points and a sentence, which is what
the "Why was this flagged?" panel shows. This is a **transparent rule-based
score, not a trained classifier**: there are no confirmed-fraud labels to train on.

## Results on the demo data (verified)

- 1,167 invoices, 35 vendors, 35 flagged as anomalies (3.0%)
- 20 of 25 invoices at least 4x their vendor's norm caught; 2/2 extreme amounts;
  8/8 overdue-and-large cases; 0 of 22 normal V112 invoices flagged
- All 17 planted duplicate pairs (34 invoices) found, none missed; 12 extra weak
  matches that look like chance near-matches
- Risk levels: 1,114 Low, 47 Medium, 6 High, 0 Critical
- A model reloaded from `anomaly_model.pkl` reproduces the stored scores exactly

## Testing

`python -m pytest` runs 31 tests from the project root:
validation (messy-file counts, clear errors), feature maths, risk-score
bounds/levels/explanations, duplicate rules (including the planted demo
duplicates), the full pipeline on the demo CSV (extreme amounts caught, no false
flags for V112), analytics/insights, and two end-to-end database tests that use a
throw-away SQLite file (never your real `data/database.db`).
The tests were also checked by deliberately breaking the code (changing a weight,
removing the vendor rule, allowing negative amounts) and confirming they fail.

## Limitations (stated plainly)

- **No accuracy, precision or recall is reported.** That needs confirmed labels
  (which invoices were truly fraudulent). Any such number here would be invented.
- The demo data is **synthetic**, and the feature choice was tuned on patterns
  planted in it. It is a sanity check, not proof of the same performance on real
  invoices, which are messier.
- Isolation Forest finds *unusual*, not *wrong*. Some flags have only a weak
  reason ("Unusual combination of values"), and 11 of the 35 flagged invoices have
  a Low risk score, because the flag and the score measure different things.
- **No Critical invoices on the demo data.** Reaching 80 needs near-maximum on
  several factors at once; thresholds were not bent to force one.
- Duplicate matching uses only amount and date. A genuinely repeating bill can be
  flagged, and the Weak tier is noisy for vendors with many invoices.
- Vendor warning rules (over 10 days late, over 8% of spend) are reasonable
  defaults, not tuned values.
- "Days overdue" for unpaid invoices is counted to the latest date in the data,
  not today's date.
- The app re-reads the database on every click, which is fine for thousands of
  invoices but would need caching for very large data.
- Single-user, local SQLite, no login.

## Future scope

Confirmed-outcome labels from real reviews would allow a supervised model and
proper metrics. Also: PDF invoice extraction (`pypdf`), fuzzy matching on
invoice numbers for duplicates, multi-currency, a user login and audit log,
scheduled re-scoring, and caching for large datasets.

## Project structure

```
InvoiceIQ/
├── app.py                     # Streamlit entry point + sidebar navigation
├── requirements.txt
├── pytest.ini
├── .streamlit/config.toml     # dark theme
├── data/sample_invoices.csv   # 1,167 synthetic invoices (database.db is created at runtime)
├── models/                    # anomaly_model.pkl, risk_model.pkl
├── src/
│   ├── generate_sample_data.py   # builds the demo CSV with planted patterns
│   ├── database.py               # SQLAlchemy tables
│   ├── preprocessing.py          # validate, clean, import
│   ├── init_demo_db.py           # reset DB + load demo CSV
│   ├── features.py               # feature engineering
│   ├── anomaly_detection.py      # Isolation Forest + reasons
│   ├── duplicate_detection.py    # duplicate rules
│   ├── risk_engine.py            # weighted score + explanations
│   ├── ml_models.py              # runs the whole pipeline, saves models
│   ├── analytics.py, insights.py # summaries and plain-English findings
│   ├── dashboard_data.py         # data layer for the UI (no Streamlit code)
│   └── ui.py                     # theme, KPI cards, chart styling
├── views/                     # one file per dashboard page
└── tests/                     # pytest suite
```
`views/` is deliberately not called `pages/`: Streamlit auto-builds its own
menu from a folder named `pages/`, which would duplicate the sidebar.

## Troubleshooting

- **`No module named 'src'`**: run helper scripts as modules from the project
  root: `python -m src.init_demo_db`, not `python src\init_demo_db.py`.
- **`streamlit` is not recognised**: use `python -m streamlit run app.py`, and
  check your prompt shows `(venv)`.
- **Prompt ends in `venv\Scripts`**: `cd` back to the project root first.
- **Install or file-lock problems on OneDrive**: move the project to a plain
  folder such as `C:\InvoiceIQ`.
- **Demo data won't load**: check `data/sample_invoices.csv` exists.

## Tech stack
Python 3.11+ · Streamlit · Pandas · NumPy · scikit-learn · Plotly · SQLite ·
SQLAlchemy · Joblib · pytest

## Fraud Lab: testing the detector against attacks

The demo data is synthetic, so there is no honest single "accuracy" number. The
Fraud Lab replaces it with something measurable: it copies your invoices in
memory (nothing is written to the database), hides simulated attacks among them,
and runs the same features, anomaly model, duplicate rules and risk score the
app always uses.

| Attack | The trick |
|---|---|
| Sudden spike | a regular vendor bills 3-6x its normal amount |
| Copy-paste duplicate | an old invoice re-entered under a new number, same amount, same or next day |
| Tweaked duplicate | same invoice, amount nudged 1-5%, date moved 2-12 days |
| Split under the limit | one large bill cut into 3 invoices just under your approval limit |
| Creeping price | a vendor raises its price ~7% with every invoice |
| Shell vendor | a new vendor sends round-number invoices in a quick burst |

How the test is kept fair:
* the anomaly model is the one trained on the clean data; it never sees the attacks
* attack invoices are unpaid and not yet due, so lateness cannot get them caught; only the trick is tested
* "caught" means at least one alarm fired (risk score at the chosen level, anomaly flag, or duplicate match);
  you can change which alarms count
* the same alarms are counted on your real invoices, so a detector that flags everything cannot look good
* a set-type attack noticed only because two amounts happened to match is shown separately as "caught by chance"
* a seed makes every run repeatable

Limits: the attacks are the ones written in `src/fraud_lab.py`. Real fraud may look different, so a
rate describes this detector against these tricks and nothing more. The misses are the point: each one
comes with the reason it slipped through and a suggestion for the rule to build next.
