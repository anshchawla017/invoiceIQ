"""
Shared test setup.

The database tests need SQLAlchemy and use a throw-away SQLite file, never
your real data/database.db. DATABASE_URL is set BEFORE src.database is
imported, which is what makes that safe.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_TMP = tempfile.mkdtemp(prefix="invoiceiq_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "test.db").replace("\\", "/")

try:
    import sqlalchemy  # noqa: F401
    HAS_SQLALCHEMY = True
except ImportError:   # lets the pure-pandas tests still run on a bare machine
    HAS_SQLALCHEMY = False
    for name in ("sqlalchemy", "sqlalchemy.orm", "src.database"):
        sys.modules[name] = MagicMock()
