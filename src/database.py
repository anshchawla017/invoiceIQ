"""
src/database.py
-----------------
The relational data layer for InvoiceIQ, using SQLAlchemy over SQLite.

Why a real database instead of "just a DataFrame"?
  - Data survives between app restarts (a DataFrame in memory doesn't).
  - Relationships (a vendor HAS MANY invoices, an invoice HAS ONE payment)
    are enforced, not just implied by matching columns.
  - We can run real SQL aggregations (SUM, GROUP BY, JOIN) for the
    analytics pages instead of re-computing everything in pandas each time.
  - It's how this would actually be built in industry.

Tables (5, as required):
  vendors            -- one row per vendor
  invoices           -- one row per invoice, FK -> vendors
  payments           -- one row per invoice's payment info, FK -> invoices
  risk_predictions   -- one row per invoice's latest risk score, FK -> invoices
  anomaly_results    -- one row per invoice's latest anomaly score, FK -> invoices

risk_predictions and anomaly_results are populated in Phase 3 once the ML
models exist; the tables are created now so the schema is final from the
start (avoids painful migrations later).
"""

import datetime
import os

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/database.db")

# check_same_thread=False is needed because Streamlit can call the DB from
# more than one thread; SQLite otherwise refuses cross-thread access.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True)
    vendor_id = Column(String, unique=True, nullable=False, index=True)
    vendor_name = Column(String, nullable=False)
    category = Column(String)

    invoices = relationship("Invoice", back_populates="vendor")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(String, unique=True, nullable=False, index=True)
    vendor_id = Column(String, ForeignKey("vendors.vendor_id"), nullable=False, index=True)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    tax = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    payment_status = Column(String, index=True)
    category = Column(String)

    vendor = relationship("Vendor", back_populates="invoices")
    payment = relationship("Payment", back_populates="invoice", uselist=False, cascade="all, delete-orphan")
    risk_prediction = relationship("RiskPrediction", back_populates="invoice", uselist=False, cascade="all, delete-orphan")
    anomaly_result = relationship("AnomalyResult", back_populates="invoice", uselist=False, cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(String, ForeignKey("invoices.invoice_id"), unique=True, nullable=False)
    payment_date = Column(Date, nullable=True)
    payment_delay = Column(Integer, nullable=True)  # days late; negative = early

    invoice = relationship("Invoice", back_populates="payment")


class RiskPrediction(Base):
    """Populated in Phase 3 by src/risk_engine.py."""
    __tablename__ = "risk_predictions"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(String, ForeignKey("invoices.invoice_id"), unique=True, nullable=False)
    risk_score = Column(Float)          # 0-100
    risk_level = Column(String)         # Low / Medium / High / Critical
    reasons = Column(Text)              # JSON-encoded list of explanation strings
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
    invoice = relationship("Invoice", back_populates="risk_prediction")


class AnomalyResult(Base):
    """Populated in Phase 3 by src/anomaly_detection.py."""
    __tablename__ = "anomaly_results"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(String, ForeignKey("invoices.invoice_id"), unique=True, nullable=False)
    anomaly_score = Column(Float)
    is_anomaly = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))

    invoice = relationship("Invoice", back_populates="anomaly_result")


def init_db():
    """Create data/ folder and all tables if they don't already exist.
    Safe to call every app startup -- create_all() is a no-op for tables
    that already exist."""
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(engine)


def get_session():
    """Get a new SQLAlchemy session. Caller is responsible for closing it
    (use as a context manager or call .close() in a finally block)."""
    return SessionLocal()


def reset_db():
    """Drop and recreate all tables. Used by 'Load Demo Dataset' when the
    user wants to start completely fresh."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
