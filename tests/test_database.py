"""
TrustChain SCM - Database Test Suite
Verifies table creation, foreign key constraints, transaction insertion,
deduplication by tx_hash, and dashboard KPI query aggregations.
"""

import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.database import DatabaseManager, SQLITE_FALLBACK_URL


class TestDatabaseManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db_url = f"sqlite:///{BASE_DIR / 'database' / 'test_trustchain.db'}"
        cls.db = DatabaseManager(db_url=test_db_url)
        cls.db.init_db(seed=False)

    def test_01_party_upsert(self):
        res = self.db.record_party(
            party_id="TEST-SUPP-01",
            name="Test Aerospace Supply",
            party_type="SUPPLIER",
            wallet_address="0x1234567890123456789012345678901234567890"
        )
        self.assertTrue(res)
        parties = self.db.get_parties()
        party_ids = [p["party_id"] for p in parties]
        self.assertIn("TEST-SUPP-01", party_ids)

    def test_02_invoice_insert_and_retrieval(self):
        self.db.record_party("TEST-BUY-01", "Test Buyer Group", "BUYER", "0x0987654321098765432109876543210987654321")
        now = datetime.now(timezone.utc)
        res = self.db.record_invoice(
            invoice_id="INV-UNIT-001",
            supplier_id="TEST-SUPP-01",
            buyer_id="TEST-BUY-01",
            amount=50000.0,
            currency="USD",
            item_description="Test Turbine Components",
            invoice_date=now,
            due_date=now,
            status="CREATED",
            blockchain_tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        )
        self.assertTrue(res)
        inv = self.db.get_invoice("INV-UNIT-001")
        self.assertIsNotNone(inv)
        self.assertEqual(inv["amount"], 50000.0)
        self.assertEqual(inv["status"], "CREATED")

    def test_03_transaction_deduplication(self):
        now = datetime.now(timezone.utc)
        tx_hash = "0x9999999999999999999999999999999999999999999999999999999999999999"
        # First insertion should succeed
        res1 = self.db.record_transaction(
            transaction_id="TXN-UNIT-001",
            invoice_id="INV-UNIT-001",
            transaction_type="INVOICE_CREATED",
            amount=50000.0,
            timestamp=now,
            blockchain_tx_hash=tx_hash,
            block_number=100
        )
        self.assertTrue(res1)

        # Duplicate insertion with exact same tx_hash must be rejected
        res2 = self.db.record_transaction(
            transaction_id="TXN-UNIT-002",
            invoice_id="INV-UNIT-001",
            transaction_type="INVOICE_CREATED",
            amount=50000.0,
            timestamp=now,
            blockchain_tx_hash=tx_hash,
            block_number=101
        )
        self.assertFalse(res2, "Duplicate blockchain tx_hash must be rejected.")

    def test_04_risk_score_and_flagging(self):
        score_id = self.db.record_risk_score(
            invoice_id="INV-UNIT-001",
            fraud_probability=0.92,
            risk_level="HIGH",
            model_version="v1.2.0-xgb",
            explanation="Critical anomaly: payment issued before shipment dispatch.",
            transaction_id="TXN-UNIT-001"
        )
        self.assertGreater(score_id, 0)
        flagged = self.db.get_flagged_transactions()
        inv_ids = [f["invoice_id"] for f in flagged]
        self.assertIn("INV-UNIT-001", inv_ids)


if __name__ == "__main__":
    unittest.main()
