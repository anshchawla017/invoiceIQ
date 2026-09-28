"""
src/init_demo_db.py
---------------------
Wipes the database and loads the bundled demo dataset fresh. This is the
exact function Phase 4's "Load Demo Dataset" button will call -- built now
so the database layer can be fully tested end-to-end before the UI exists.

Run:
    python src/init_demo_db.py
"""

import json

from src.database import reset_db
from src.preprocessing import load_and_import_csv

DEMO_CSV_PATH = "data/sample_invoices.csv"


def load_demo_dataset() -> dict:
    reset_db()
    report = load_and_import_csv(DEMO_CSV_PATH, replace_existing=False)
    return report


if __name__ == "__main__":
    report = load_demo_dataset()
    print(json.dumps(report, indent=2))
