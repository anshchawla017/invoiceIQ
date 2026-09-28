"""End-to-end database tests. Skipped automatically if SQLAlchemy is missing."""

import pytest

from tests.conftest import HAS_SQLALCHEMY
from tests.helpers import DEMO_CSV

pytestmark = pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")


def test_demo_import_score_and_reimport():
    from src.database import Invoice, RiskPrediction, AnomalyResult, get_session, init_db, reset_db
    from src.ml_models import run_full_analysis
    from src.preprocessing import load_and_import_csv

    init_db(); reset_db()
    report = load_and_import_csv(DEMO_CSV)
    assert report["inserted"] == 1167

    summary = run_full_analysis()
    assert summary["invoices_analysed"] == 1167

    s = get_session()
    try:
        assert s.query(Invoice).count() == 1167
        assert s.query(RiskPrediction).count() == 1167
        assert s.query(AnomalyResult).count() == 1167
    finally:
        s.close()

    again = load_and_import_csv(DEMO_CSV)          # importing twice must not duplicate
    assert again["inserted"] == 0 and again["skipped_existing"] == 1167


def test_empty_database_gives_friendly_error():
    from src.database import init_db, reset_db
    from src.ml_models import run_full_analysis
    init_db(); reset_db()
    with pytest.raises(ValueError):
        run_full_analysis()
