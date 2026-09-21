"""
TrustChain SCM - Database Manager
Dual-engine abstraction supporting PostgreSQL and resilient local SQLite fallback.
Provides thread-safe access, schema initialization, seed data loading,
and querying for the dashboard, listener, and AI model.
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import sqlalchemy as sa
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String,
    Float, Numeric, DateTime, Text, Boolean, ForeignKey, Index,
    select, insert, update, desc, and_, text
)
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

logger = logging.getLogger("trustchain.database")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_FALLBACK_URL = f"sqlite:///{DB_DIR / 'trustchain.db'}"

metadata = MetaData()

# Define schema tables using SQLAlchemy MetaData
parties_table = Table(
    "parties",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("party_id", String(64), unique=True, nullable=False),
    Column("name", String(255), nullable=False),
    Column("party_type", String(32), nullable=False),
    Column("wallet_address", String(42), nullable=False),
    Column("risk_rating", String(16), default="STANDARD"),
    Column("country", String(64), default="USA"),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
)

invoices_table = Table(
    "invoices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("invoice_id", String(64), unique=True, nullable=False),
    Column("supplier_id", String(64), ForeignKey("parties.party_id", ondelete="CASCADE"), nullable=False),
    Column("buyer_id", String(64), ForeignKey("parties.party_id", ondelete="CASCADE"), nullable=False),
    Column("amount", Float, nullable=False),
    Column("currency", String(8), default="USD"),
    Column("item_description", Text, nullable=True),
    Column("invoice_date", DateTime, nullable=False),
    Column("due_date", DateTime, nullable=False),
    Column("status", String(32), default="CREATED"),
    Column("blockchain_tx_hash", String(66), nullable=True),
    Column("block_number", Integer, default=0),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime, default=lambda: datetime.now(timezone.utc)),
)

shipments_table = Table(
    "shipments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("shipment_id", String(64), unique=True, nullable=False),
    Column("invoice_id", String(64), ForeignKey("invoices.invoice_id", ondelete="CASCADE"), nullable=False),
    Column("carrier", String(128), nullable=False),
    Column("tracking_number", String(128), nullable=False),
    Column("shipment_date", DateTime, nullable=False),
    Column("status", String(32), default="DISPATCHED"),
    Column("blockchain_tx_hash", String(66), nullable=True),
    Column("block_number", Integer, default=0),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
)

transactions_table = Table(
    "transactions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("transaction_id", String(64), unique=True, nullable=False),
    Column("invoice_id", String(64), ForeignKey("invoices.invoice_id", ondelete="CASCADE"), nullable=False),
    Column("transaction_type", String(64), nullable=False),
    Column("amount", Float, default=0.0),
    Column("sender_address", String(42), nullable=True),
    Column("receiver_address", String(42), nullable=True),
    Column("timestamp", DateTime, nullable=False),
    Column("blockchain_tx_hash", String(66), unique=True, nullable=False),
    Column("block_number", Integer, default=0),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
)

risk_scores_table = Table(
    "risk_scores",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("transaction_id", String(64), ForeignKey("transactions.transaction_id", ondelete="SET NULL"), nullable=True),
    Column("invoice_id", String(64), ForeignKey("invoices.invoice_id", ondelete="CASCADE"), nullable=False),
    Column("fraud_probability", Float, nullable=False),
    Column("default_probability", Float, default=0.0),
    Column("risk_level", String(16), nullable=False),
    Column("model_version", String(64), nullable=False),
    Column("explanation", Text, nullable=True),
    Column("top_features", Text, nullable=True),
    Column("shap_summary", Text, nullable=True),
    Column("is_flagged", Boolean, default=False),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
)


class DatabaseManager:
    """Manages database connectivity, queries, and migrations across PostgreSQL / SQLite."""

    def __init__(self, db_url: Optional[str] = None):
        self.raw_url = db_url or os.getenv("DATABASE_URL") or SQLITE_FALLBACK_URL
        self.is_postgres = False
        self.engine = self._create_engine_with_fallback(self.raw_url)
        self.SessionFactory = sessionmaker(bind=self.engine)

    def _create_engine_with_fallback(self, url: str) -> sa.engine.Engine:
        """Attempts connection to specified URL, falling back to SQLite if PostgreSQL fails."""
        if url.startswith("postgresql"):
            try:
                engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                self.is_postgres = True
                logger.info(f"Connected successfully to PostgreSQL database.")
                return engine
            except Exception as ex:
                logger.warning(
                    f"Could not connect to PostgreSQL at {url} ({ex}). "
                    f"Falling back gracefully to local resilient SQLite storage."
                )

        # Fallback to local SQLite
        sqlite_engine = create_engine(
            SQLITE_FALLBACK_URL,
            connect_args={"check_same_thread": False}
        )
        # Enable SQLite foreign key constraints
        @sa.event.listens_for(sqlite_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        logger.info(f"Connected to local SQLite database: {SQLITE_FALLBACK_URL}")
        self.is_postgres = False
        return sqlite_engine

    def init_db(self, seed: bool = True):
        """Creates all relational tables and seeds with realistic scenario records."""
        logger.info("Initializing database schema...")
        metadata.create_all(self.engine)

        if seed:
            self.seed_if_empty()

    def seed_if_empty(self):
        """Loads default seed data if database tables are currently empty."""
        with self.engine.connect() as conn:
            result = conn.execute(select(sa.func.count()).select_from(invoices_table)).scalar()
            if result and result > 0:
                logger.info(f"Database already populated ({result} invoices found). Skipping initial seed.")
                return

        logger.info("Database is empty. Populating with realistic supply chain seed records...")
        self._load_seed_records()

    def _load_seed_records(self):
        """Executes seed insertion of parties, invoices, shipments, transactions, and risk scores."""
        now = datetime.now(timezone.utc)
        parties = [
            {"party_id": "SUPP-GLOBAL-01", "name": "AeroTech Components Ltd", "party_type": "SUPPLIER", "wallet_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "risk_rating": "AAA", "country": "Germany"},
            {"party_id": "SUPP-NEXUS-02",  "name": "Apex Precision Sensors",  "party_type": "SUPPLIER", "wallet_address": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC", "risk_rating": "A", "country": "Japan"},
            {"party_id": "SUPP-TITAN-03",  "name": "Titan Raw Materials Corp","party_type": "SUPPLIER", "wallet_address": "0x90F79bf6EB2c4f870365E785982E1f101E93b906", "risk_rating": "BBB", "country": "South Korea"},
            {"party_id": "SUPP-SUSP-04",   "name": "ShadowShell Holdings Inc", "party_type": "SUPPLIER", "wallet_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65", "risk_rating": "HIGH_RISK", "country": "Seychelles"},
            {"party_id": "BUYER-OMEGA-01", "name": "Omega Automotive Group",  "party_type": "BUYER",    "wallet_address": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc", "risk_rating": "AAA", "country": "USA"},
            {"party_id": "BUYER-VORTEX-02","name": "Vortex Aerospace Inc",   "party_type": "BUYER",    "wallet_address": "0x976EA74026E726554dB657fA54763abd0C3a0aa9", "risk_rating": "AA", "country": "USA"},
            {"party_id": "BUYER-QUICK-03", "name": "FlashRetail Logistics",   "party_type": "BUYER",    "wallet_address": "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955", "risk_rating": "HIGH_RISK", "country": "Panama"},
            {"party_id": "LEND-ALPHA-01",  "name": "LiquidityBridge Capital", "party_type": "LENDER",   "wallet_address": "0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f", "risk_rating": "AAA", "country": "UK"},
            {"party_id": "LEND-BETA-02",   "name": "TradeFlow Global Credit", "party_type": "LENDER",   "wallet_address": "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720", "risk_rating": "AAA", "country": "Switzerland"},
        ]

        invoices = [
            {"invoice_id": "INV-2026-001", "supplier_id": "SUPP-GLOBAL-01", "buyer_id": "BUYER-OMEGA-01", "amount": 125000.00, "currency": "USD", "item_description": "500x Titanium Turbine Blades Grade 5", "invoice_date": datetime(2026, 9, 1, 8, 30), "due_date": datetime(2026, 10, 31), "status": "PAID", "blockchain_tx_hash": "0x3a4b7f8c9d0e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b", "block_number": 18450100},
            {"invoice_id": "INV-2026-002", "supplier_id": "SUPP-NEXUS-02",  "buyer_id": "BUYER-VORTEX-02", "amount": 88500.00,  "currency": "USD", "item_description": "1200x MEMS Gyroscope Precision Sensors", "invoice_date": datetime(2026, 9, 3, 10, 15), "due_date": datetime(2026, 11, 3), "status": "FINANCED", "blockchain_tx_hash": "0x1f2e3d4c5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e", "block_number": 18450250},
            {"invoice_id": "INV-2026-003", "supplier_id": "SUPP-TITAN-03",  "buyer_id": "BUYER-OMEGA-01", "amount": 310000.00, "currency": "USD", "item_description": "40 Metric Tons Structural Aluminum", "invoice_date": datetime(2026, 9, 5, 14, 0), "due_date": datetime(2026, 12, 5), "status": "SHIPMENT_CONFIRMED", "blockchain_tx_hash": "0x8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b", "block_number": 18450420},
            {"invoice_id": "INV-2026-004", "supplier_id": "SUPP-SUSP-04",   "buyer_id": "BUYER-QUICK-03", "amount": 450000.00, "currency": "USD", "item_description": "High-Frequency Semiconductor Wafers (Unverified)", "invoice_date": datetime(2026, 9, 8, 2, 11), "due_date": datetime(2026, 9, 10), "status": "FLAGGED_FRAUD", "blockchain_tx_hash": "0x99a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8", "block_number": 18450600},
            {"invoice_id": "INV-2026-005", "supplier_id": "SUPP-GLOBAL-01", "buyer_id": "BUYER-VORTEX-02", "amount": 64200.00,  "currency": "USD", "item_description": "High-temp Ceramic Exhaust Couplings", "invoice_date": datetime(2026, 9, 10, 11, 20), "due_date": datetime(2026, 11, 10), "status": "PAID", "blockchain_tx_hash": "0x4f5e6d7c8b9a0f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e", "block_number": 18450780},
            {"invoice_id": "INV-2026-006", "supplier_id": "SUPP-SUSP-04",   "buyer_id": "BUYER-OMEGA-01", "amount": 500000.00, "currency": "USD", "item_description": "Bulk Specialized Rare Earth Elements", "invoice_date": datetime(2026, 9, 12, 23, 45), "due_date": datetime(2026, 9, 25), "status": "FLAGGED_FRAUD", "blockchain_tx_hash": "0x7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d", "block_number": 18450910},
            {"invoice_id": "INV-2026-007", "supplier_id": "SUPP-NEXUS-02",  "buyer_id": "BUYER-OMEGA-01", "amount": 42000.00,  "currency": "USD", "item_description": "Automated Optical Inspection Modules", "invoice_date": datetime(2026, 9, 14, 9, 0), "due_date": datetime(2026, 11, 14), "status": "CREATED", "blockchain_tx_hash": "0x5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a", "block_number": 18451120},
            {"invoice_id": "INV-2026-008", "supplier_id": "SUPP-SUSP-04",   "buyer_id": "BUYER-QUICK-03", "amount": 250000.00, "currency": "USD", "item_description": "Consulting & IP Licensing Receivables", "invoice_date": datetime(2026, 9, 15, 3, 14), "due_date": datetime(2026, 9, 20), "status": "FLAGGED_FRAUD", "blockchain_tx_hash": "0x6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d", "block_number": 18451300},
            {"invoice_id": "INV-2026-009", "supplier_id": "SUPP-TITAN-03",  "buyer_id": "BUYER-VORTEX-02", "amount": 175000.00, "currency": "USD", "item_description": "Reinforced Carbon Composite Panels", "invoice_date": datetime(2026, 9, 17, 13, 40), "due_date": datetime(2026, 11, 30), "status": "PAID", "blockchain_tx_hash": "0x2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b", "block_number": 18451480},
            {"invoice_id": "INV-2026-010", "supplier_id": "SUPP-GLOBAL-01", "buyer_id": "BUYER-OMEGA-01", "amount": 94000.00,  "currency": "USD", "item_description": "Cryogenic Valves and Actuators Batch #4", "invoice_date": datetime(2026, 9, 19, 16, 15), "due_date": datetime(2026, 11, 19), "status": "CREATED", "blockchain_tx_hash": "0x1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e", "block_number": 18451650},
        ]

        shipments = [
            {"shipment_id": "SHIP-2026-001", "invoice_id": "INV-2026-001", "carrier": "DHL Global Express", "tracking_number": "DHL-7739182390", "shipment_date": datetime(2026, 9, 3, 14, 0), "status": "DELIVERED", "blockchain_tx_hash": "0xaa11bb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66", "block_number": 18450150},
            {"shipment_id": "SHIP-2026-002", "invoice_id": "INV-2026-002", "carrier": "FedEx International", "tracking_number": "FDX-9928192019", "shipment_date": datetime(2026, 9, 5, 10, 30), "status": "IN_TRANSIT", "blockchain_tx_hash": "0xbb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77", "block_number": 18450280},
            {"shipment_id": "SHIP-2026-003", "invoice_id": "INV-2026-003", "carrier": "Maersk Ocean Freight","tracking_number": "MSK-4481029481", "shipment_date": datetime(2026, 9, 8, 8, 0),   "status": "DISPATCHED", "blockchain_tx_hash": "0xcc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88", "block_number": 18450460},
            {"shipment_id": "SHIP-2026-005", "invoice_id": "INV-2026-005", "carrier": "Kuehne+Nagel Logistics","tracking_number": "KNN-3391028471", "shipment_date": datetime(2026, 9, 12, 11, 0), "status": "DELIVERED", "blockchain_tx_hash": "0xdd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99", "block_number": 18450810},
            {"shipment_id": "SHIP-2026-009", "invoice_id": "INV-2026-009", "carrier": "DB Schenker Global",   "tracking_number": "DBS-1102938472", "shipment_date": datetime(2026, 9, 18, 15, 20), "status": "DELIVERED", "blockchain_tx_hash": "0xee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99bb00", "block_number": 18451510},
        ]

        transactions = [
            {"transaction_id": "TXN-2026-001A", "invoice_id": "INV-2026-001", "transaction_type": "INVOICE_CREATED", "amount": 125000.00, "sender_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "receiver_address": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc", "timestamp": datetime(2026, 9, 1, 8, 30), "blockchain_tx_hash": "0x3a4b7f8c9d0e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b", "block_number": 18450100},
            {"transaction_id": "TXN-2026-001B", "invoice_id": "INV-2026-001", "transaction_type": "SHIPMENT_CONFIRMED", "amount": 0.00, "sender_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "receiver_address": "0x0000000000000000000000000000000000000000", "timestamp": datetime(2026, 9, 3, 14, 0), "blockchain_tx_hash": "0xaa11bb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66", "block_number": 18450150},
            {"transaction_id": "TXN-2026-001C", "invoice_id": "INV-2026-001", "transaction_type": "PAYMENT_RELEASED", "amount": 125000.00, "sender_address": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc", "receiver_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "timestamp": datetime(2026, 9, 15, 16, 30), "blockchain_tx_hash": "0x55aa66bb77cc88dd99ee00ff11aa22bb33cc44dd55ee66ff77aa88bb99cc00dd", "block_number": 18450190},
            {"transaction_id": "TXN-2026-004A", "invoice_id": "INV-2026-004", "transaction_type": "INVOICE_CREATED", "amount": 450000.00, "sender_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65", "receiver_address": "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955", "timestamp": datetime(2026, 9, 8, 2, 11), "blockchain_tx_hash": "0x99a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8", "block_number": 18450600},
            {"transaction_id": "TXN-2026-004B", "invoice_id": "INV-2026-004", "transaction_type": "PAYMENT_RELEASED", "amount": 450000.00, "sender_address": "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955", "receiver_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65", "timestamp": datetime(2026, 9, 8, 4, 15), "blockchain_tx_hash": "0x8899aabbccddeeff00112233445566778899aabbccddeeff0011223344556677", "block_number": 18450610},
            {"transaction_id": "TXN-2026-005A", "invoice_id": "INV-2026-005", "transaction_type": "INVOICE_CREATED", "amount": 64200.00,  "sender_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "receiver_address": "0x976EA74026E726554dB657fA54763abd0C3a0aa9", "timestamp": datetime(2026, 9, 10, 11, 20), "blockchain_tx_hash": "0x4f5e6d7c8b9a0f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e", "block_number": 18450780},
            {"transaction_id": "TXN-2026-005B", "invoice_id": "INV-2026-005", "transaction_type": "SHIPMENT_CONFIRMED", "amount": 0.00, "sender_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "receiver_address": "0x0000000000000000000000000000000000000000", "timestamp": datetime(2026, 9, 12, 11, 0), "blockchain_tx_hash": "0xdd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99", "block_number": 18450810},
            {"transaction_id": "TXN-2026-005C", "invoice_id": "INV-2026-005", "transaction_type": "PAYMENT_RELEASED", "amount": 64200.00,  "sender_address": "0x976EA74026E726554dB657fA54763abd0C3a0aa9", "receiver_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "timestamp": datetime(2026, 9, 20, 14, 10), "blockchain_tx_hash": "0x77889900aabbccddeeff00112233445566778899aabbccddeeff001122334455", "block_number": 18450890},
            {"transaction_id": "TXN-2026-006A", "invoice_id": "INV-2026-006", "transaction_type": "INVOICE_CREATED", "amount": 500000.00, "sender_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65", "receiver_address": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc", "timestamp": datetime(2026, 9, 12, 23, 45), "blockchain_tx_hash": "0x7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d", "block_number": 18450910},
            {"transaction_id": "TXN-2026-008A", "invoice_id": "INV-2026-008", "transaction_type": "INVOICE_CREATED", "amount": 250000.00, "sender_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65", "receiver_address": "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955", "timestamp": datetime(2026, 9, 15, 3, 14), "blockchain_tx_hash": "0x6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d", "block_number": 18451300},
            {"transaction_id": "TXN-2026-008B", "invoice_id": "INV-2026-008", "transaction_type": "FINANCING_REQUESTED", "amount": 250000.00, "sender_address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65", "receiver_address": "0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f", "timestamp": datetime(2026, 9, 15, 3, 18), "blockchain_tx_hash": "0x11223344556677889900aabbccddeeff00112233445566778899aabbccddeeff", "block_number": 18451310},
        ]

        risk_scores = [
            {
                "transaction_id": "TXN-2026-001C", "invoice_id": "INV-2026-001", "fraud_probability": 0.042, "default_probability": 0.015,
                "risk_level": "LOW", "model_version": "v1.2.0-xgb",
                "explanation": "Transaction displays verified physical delivery by Tier-1 carrier, typical settlement cadence (12 days), and counterparties with 100% verified fulfillment history.",
                "top_features": json.dumps({"carrier_verification": -0.42, "settlement_delay_norm": -0.38, "counterparty_rating": -0.35}),
                "shap_summary": "Normal commercial flow. Negligible fraud risk.", "is_flagged": False
            },
            {
                "transaction_id": "TXN-2026-004B", "invoice_id": "INV-2026-004", "fraud_probability": 0.946, "default_probability": 0.820,
                "risk_level": "HIGH", "model_version": "v1.2.0-xgb",
                "explanation": "CRITICAL ANOMALY: Settlement released only 2.06 hours after invoice creation with no physical shipment confirmation. Counterparty previously flagged in suspicious entities registry.",
                "top_features": json.dumps({"ghost_shipment_flag": 0.88, "payment_speed_anomaly": 0.76, "supplier_risk_tier": 0.64, "round_amount_score": 0.32}),
                "shap_summary": "Ghost shipment anomaly. Rapid round-sum liquidation detected.", "is_flagged": True
            },
            {
                "transaction_id": "TXN-2026-005C", "invoice_id": "INV-2026-005", "fraud_probability": 0.068, "default_probability": 0.021,
                "risk_level": "LOW", "model_version": "v1.2.0-xgb",
                "explanation": "Standard aerospace parts batch fulfillment with verified carrier tracking, standard Net-30 payment schedule, and consistent amount history.",
                "top_features": json.dumps({"carrier_verification": -0.36, "time_delta_realistic": -0.31, "amount_variance_low": -0.28}),
                "shap_summary": "Normal commercial flow. Verified logistics chain.", "is_flagged": False
            },
            {
                "transaction_id": "TXN-2026-006A", "invoice_id": "INV-2026-006", "fraud_probability": 0.882, "default_probability": 0.740,
                "risk_level": "HIGH", "model_version": "v1.2.0-xgb",
                "explanation": "HIGH RISK: Unusually large round-sum invoice ($500,000) issued during non-business hours (23:45 UTC) from an entity with elevated fraud history.",
                "top_features": json.dumps({"amount_deviation_extreme": 0.81, "off_hours_timestamp": 0.52, "supplier_prior_flags": 0.69}),
                "shap_summary": "Potential duplicate or phantom receivable submission.", "is_flagged": True
            },
            {
                "transaction_id": "TXN-2026-008B", "invoice_id": "INV-2026-008", "fraud_probability": 0.894, "default_probability": 0.790,
                "risk_level": "HIGH", "model_version": "v1.2.0-xgb",
                "explanation": "HIGH RISK: Immediate 100% receivables financing request submitted 4 minutes after invoice creation with no Bill of Lading attached. Shell entity behavior.",
                "top_features": json.dumps({"financing_timing_immediate": 0.85, "missing_bol": 0.72, "supplier_fraud_rating": 0.61}),
                "shap_summary": "Early financing fraud vector identified.", "is_flagged": True
            },
        ]

        with self.engine.begin() as conn:
            conn.execute(insert(parties_table), parties)
            conn.execute(insert(invoices_table), invoices)
            conn.execute(insert(shipments_table), shipments)
            conn.execute(insert(transactions_table), transactions)
            conn.execute(insert(risk_scores_table), risk_scores)

        logger.info("Seed data loaded successfully.")

    # ---------------- CRUD & Queries ----------------

    def record_party(self, party_id: str, name: str, party_type: str, wallet_address: str, risk_rating: str = "STANDARD", country: str = "USA") -> bool:
        """Upserts a party in the database."""
        with self.engine.begin() as conn:
            existing = conn.execute(select(parties_table.c.id).where(parties_table.c.party_id == party_id)).first()
            if existing:
                conn.execute(
                    update(parties_table).where(parties_table.c.party_id == party_id).values(
                        name=name, party_type=party_type, wallet_address=wallet_address, risk_rating=risk_rating, country=country
                    )
                )
            else:
                conn.execute(
                    insert(parties_table).values(
                        party_id=party_id, name=name, party_type=party_type, wallet_address=wallet_address, risk_rating=risk_rating, country=country
                    )
                )
        return True

    def record_invoice(
        self,
        invoice_id: str,
        supplier_id: str,
        buyer_id: str,
        amount: float,
        currency: str,
        item_description: str,
        invoice_date: datetime,
        due_date: datetime,
        status: str,
        blockchain_tx_hash: Optional[str] = None,
        block_number: int = 0
    ) -> bool:
        """Inserts or updates an invoice."""
        with self.engine.begin() as conn:
            existing = conn.execute(select(invoices_table.c.id).where(invoices_table.c.invoice_id == invoice_id)).first()
            if existing:
                conn.execute(
                    update(invoices_table).where(invoices_table.c.invoice_id == invoice_id).values(
                        status=status,
                        blockchain_tx_hash=blockchain_tx_hash,
                        block_number=block_number,
                        updated_at=datetime.now(timezone.utc)
                    )
                )
            else:
                conn.execute(
                    insert(invoices_table).values(
                        invoice_id=invoice_id,
                        supplier_id=supplier_id,
                        buyer_id=buyer_id,
                        amount=amount,
                        currency=currency,
                        item_description=item_description,
                        invoice_date=invoice_date,
                        due_date=due_date,
                        status=status,
                        blockchain_tx_hash=blockchain_tx_hash,
                        block_number=block_number
                    )
                )
        return True

    def record_shipment(
        self,
        shipment_id: str,
        invoice_id: str,
        carrier: str,
        tracking_number: str,
        shipment_date: datetime,
        status: str,
        blockchain_tx_hash: Optional[str] = None,
        block_number: int = 0
    ) -> bool:
        """Records shipment logistics details."""
        with self.engine.begin() as conn:
            existing = conn.execute(select(shipments_table.c.id).where(shipments_table.c.shipment_id == shipment_id)).first()
            if not existing:
                conn.execute(
                    insert(shipments_table).values(
                        shipment_id=shipment_id,
                        invoice_id=invoice_id,
                        carrier=carrier,
                        tracking_number=tracking_number,
                        shipment_date=shipment_date,
                        status=status,
                        blockchain_tx_hash=blockchain_tx_hash,
                        block_number=block_number
                    )
                )
                # Also update invoice status to SHIPMENT_CONFIRMED if not paid
                conn.execute(
                    update(invoices_table)
                    .where(and_(invoices_table.c.invoice_id == invoice_id, invoices_table.c.status != "PAID"))
                    .values(status="SHIPMENT_CONFIRMED", updated_at=datetime.now(timezone.utc))
                )
        return True

    def record_transaction(
        self,
        transaction_id: str,
        invoice_id: str,
        transaction_type: str,
        amount: float,
        timestamp: datetime,
        blockchain_tx_hash: str,
        sender_address: Optional[str] = None,
        receiver_address: Optional[str] = None,
        block_number: int = 0
    ) -> bool:
        """Records an on-chain transaction event, ensuring no duplicate tx_hash is inserted."""
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(transactions_table.c.id).where(transactions_table.c.blockchain_tx_hash == blockchain_tx_hash)
            ).first()
            if existing:
                logger.info(f"Transaction with tx_hash {blockchain_tx_hash} already recorded. Skipping duplicate.")
                return False

            conn.execute(
                insert(transactions_table).values(
                    transaction_id=transaction_id,
                    invoice_id=invoice_id,
                    transaction_type=transaction_type,
                    amount=amount,
                    sender_address=sender_address,
                    receiver_address=receiver_address,
                    timestamp=timestamp,
                    blockchain_tx_hash=blockchain_tx_hash,
                    block_number=block_number
                )
            )
        return True

    def record_risk_score(
        self,
        invoice_id: str,
        fraud_probability: float,
        risk_level: str,
        model_version: str,
        explanation: str,
        top_features: Optional[str] = None,
        shap_summary: Optional[str] = None,
        transaction_id: Optional[str] = None,
        default_probability: float = 0.0
    ) -> int:
        """Records ML risk assessment score and updates invoice flag status if HIGH risk."""
        is_flagged = risk_level.upper() == "HIGH" or fraud_probability >= float(os.getenv("RISK_THRESHOLD_HIGH", "0.70"))
        with self.engine.begin() as conn:
            result = conn.execute(
                insert(risk_scores_table).values(
                    transaction_id=transaction_id,
                    invoice_id=invoice_id,
                    fraud_probability=fraud_probability,
                    default_probability=default_probability,
                    risk_level=risk_level,
                    model_version=model_version,
                    explanation=explanation,
                    top_features=top_features,
                    shap_summary=shap_summary,
                    is_flagged=is_flagged
                )
            )
            score_id = result.inserted_primary_key[0] if result.inserted_primary_key else 0

            # If high risk, mark the invoice as FLAGGED_FRAUD
            if is_flagged:
                conn.execute(
                    update(invoices_table)
                    .where(invoices_table.c.invoice_id == invoice_id)
                    .values(status="FLAGGED_FRAUD", updated_at=datetime.now(timezone.utc))
                )
        return score_id

    # ---------------- Dashboard & Analytics Queries ----------------

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Calculates aggregated KPIs for the executive dashboard."""
        with self.engine.connect() as conn:
            total_invoices = conn.execute(select(sa.func.count()).select_from(invoices_table)).scalar() or 0
            total_txns = conn.execute(select(sa.func.count()).select_from(transactions_table)).scalar() or 0

            total_volume = conn.execute(
                select(sa.func.sum(invoices_table.c.amount))
            ).scalar() or 0.0

            paid_volume = conn.execute(
                select(sa.func.sum(transactions_table.c.amount))
                .where(transactions_table.c.transaction_type == "PAYMENT_RELEASED")
            ).scalar() or 0.0

            flagged_invoices = conn.execute(
                select(sa.func.count()).select_from(invoices_table)
                .where(invoices_table.c.status == "FLAGGED_FRAUD")
            ).scalar() or 0

            avg_risk = conn.execute(
                select(sa.func.avg(risk_scores_table.c.fraud_probability))
            ).scalar() or 0.0

            fraud_rate = (flagged_invoices / total_invoices * 100.0) if total_invoices > 0 else 0.0

            return {
                "total_invoices": total_invoices,
                "total_transactions": total_txns,
                "total_volume": float(total_volume),
                "total_paid_volume": float(paid_volume),
                "flagged_transactions": flagged_invoices,
                "average_risk_score": float(avg_risk),
                "fraud_rate": round(fraud_rate, 2),
            }

    def get_all_invoices(self) -> List[Dict[str, Any]]:
        """Returns all invoices with supplier and buyer details."""
        stmt = (
            select(
                invoices_table,
                parties_table.c.name.label("supplier_name")
            )
            .select_from(
                invoices_table.join(parties_table, invoices_table.c.supplier_id == parties_table.c.party_id)
            )
            .order_by(desc(invoices_table.c.invoice_date))
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
            return [dict(r) for r in rows]

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a single invoice by ID."""
        with self.engine.connect() as conn:
            row = conn.execute(select(invoices_table).where(invoices_table.c.invoice_id == invoice_id)).mappings().first()
            return dict(row) if row else None

    def get_invoice_audit_trail(self, invoice_id: str) -> Dict[str, Any]:
        """Compiles complete provenance audit trail for an invoice."""
        with self.engine.connect() as conn:
            inv = conn.execute(select(invoices_table).where(invoices_table.c.invoice_id == invoice_id)).mappings().first()
            if not inv:
                return {}

            txns = conn.execute(
                select(transactions_table)
                .where(transactions_table.c.invoice_id == invoice_id)
                .order_by(transactions_table.c.timestamp)
            ).mappings().all()

            shipments = conn.execute(
                select(shipments_table).where(shipments_table.c.invoice_id == invoice_id)
            ).mappings().all()

            risks = conn.execute(
                select(risk_scores_table)
                .where(risk_scores_table.c.invoice_id == invoice_id)
                .order_by(desc(risk_scores_table.c.created_at))
            ).mappings().all()

            return {
                "invoice": dict(inv),
                "transactions": [dict(t) for t in txns],
                "shipments": [dict(s) for s in shipments],
                "risk_scores": [dict(r) for r in risks],
            }

    def get_transactions(self, limit: int = 100, risk_level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns transactions combined with risk scores and counterparties."""
        stmt = (
            select(
                transactions_table,
                invoices_table.c.amount.label("invoice_amount"),
                invoices_table.c.supplier_id,
                invoices_table.c.buyer_id,
                invoices_table.c.status.label("invoice_status"),
                risk_scores_table.c.fraud_probability,
                risk_scores_table.c.risk_level,
                risk_scores_table.c.is_flagged
            )
            .select_from(
                transactions_table
                .join(invoices_table, transactions_table.c.invoice_id == invoices_table.c.invoice_id)
                .outerjoin(risk_scores_table, transactions_table.c.transaction_id == risk_scores_table.c.transaction_id)
            )
            .order_by(desc(transactions_table.c.timestamp))
            .limit(limit)
        )
        if risk_level:
            stmt = stmt.where(risk_scores_table.c.risk_level == risk_level)

        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
            return [dict(r) for r in rows]

    def get_flagged_transactions(self) -> List[Dict[str, Any]]:
        """Returns all transactions or invoices flagged with HIGH fraud risk."""
        stmt = (
            select(
                risk_scores_table,
                invoices_table.c.amount.label("invoice_amount"),
                invoices_table.c.supplier_id,
                invoices_table.c.buyer_id,
                invoices_table.c.item_description,
                invoices_table.c.blockchain_tx_hash.label("inv_tx_hash"),
                transactions_table.c.transaction_type,
                transactions_table.c.amount.label("tx_amount"),
                transactions_table.c.blockchain_tx_hash.label("tx_hash")
            )
            .select_from(
                risk_scores_table
                .join(invoices_table, risk_scores_table.c.invoice_id == invoices_table.c.invoice_id)
                .outerjoin(transactions_table, risk_scores_table.c.transaction_id == transactions_table.c.transaction_id)
            )
            .where(risk_scores_table.c.is_flagged == True)
            .order_by(desc(risk_scores_table.c.fraud_probability))
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
            return [dict(r) for r in rows]

    def get_parties(self) -> List[Dict[str, Any]]:
        """Returns all ecosystem participants."""
        with self.engine.connect() as conn:
            rows = conn.execute(select(parties_table).order_by(parties_table.c.name)).mappings().all()
            return [dict(r) for r in rows]

    def get_recent_blockchain_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns latest on-chain events for the blockchain explorer view."""
        stmt = (
            select(
                transactions_table.c.transaction_id,
                transactions_table.c.invoice_id,
                transactions_table.c.transaction_type,
                transactions_table.c.amount,
                transactions_table.c.blockchain_tx_hash,
                transactions_table.c.block_number,
                transactions_table.c.sender_address,
                transactions_table.c.receiver_address,
                transactions_table.c.timestamp
            )
            .order_by(desc(transactions_table.c.block_number), desc(transactions_table.c.timestamp))
            .limit(limit)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
            return [dict(r) for r in rows]


# Global singleton database instance
db = DatabaseManager()

if __name__ == "__main__":
    db.init_db(seed=True)
    metrics = db.get_dashboard_metrics()
    print("Database Initialized successfully.")
    print("Dashboard Metrics:", json.dumps(metrics, indent=2))
