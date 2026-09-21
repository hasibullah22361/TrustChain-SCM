"""
TrustChain SCM - End-to-End Integration Test Suite
Validates the complete 18-step supply chain lifecycle from blockchain event simulation
to SQL database ingestion, XGBoost risk evaluation, SHAP explainability, and audit trail verification.
"""

import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.database import db
from listener.simulator import simulator
from model.predict import predict_transaction_risk
from model.explain import explain_transaction_risk


class TestTrustChainEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db(seed=True)

    def test_complete_clean_trade_lifecycle(self):
        """Tests standard normal invoice lifecycle through to low-risk clearance."""
        inv_id = "INV-E2E-CLEAN-01"
        supp_wallet = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
        buyer_wallet = "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"
        t_base = datetime.now(timezone.utc) - timedelta(days=25)

        # 1. Simulate on-chain InvoiceCreated
        evt_inv = simulator.simulate_invoice_creation(
            invoice_id=inv_id,
            supplier_id="SUPP-GLOBAL-01",
            buyer_id="BUYER-OMEGA-01",
            amount=115000.0,
            item_description="Aerospace Structural Fasteners",
            supplier_wallet=supp_wallet,
            buyer_wallet=buyer_wallet,
            created_time=t_base
        )
        self.assertEqual(evt_inv["status"], "CREATED")
        self.assertTrue(evt_inv["tx_hash"].startswith("0x"))

        # 2. Simulate on-chain ShipmentConfirmed
        t_ship = t_base + timedelta(days=3)
        evt_ship = simulator.simulate_shipment_confirmation(
            invoice_id=inv_id,
            carrier="DHL Global Express",
            tracking_number="DHL-E2E-991823",
            supplier_wallet=supp_wallet,
            shipment_time=t_ship
        )
        self.assertEqual(evt_ship["status"], "SHIPMENT_CONFIRMED")

        # 3. Simulate on-chain PaymentReleased
        t_pay = t_base + timedelta(days=20)
        evt_pay = simulator.simulate_payment_release(
            invoice_id=inv_id,
            amount_paid=115000.0,
            buyer_wallet=buyer_wallet,
            supplier_wallet=supp_wallet,
            payment_time=t_pay
        )
        self.assertEqual(evt_pay["status"], "PAID")

        # 4. Ingestion Check: Verify SQL transactions and invoice updates
        inv_record = db.get_invoice(inv_id)
        self.assertIsNotNone(inv_record)
        self.assertEqual(inv_record["status"], "PAID")

        # 5. AI Risk Scoring & SHAP Explanation
        sample_feature_data = {
            "invoice_amount": 115000.0,
            "transaction_amount": 115000.0,
            "carrier": "DHL Global Express",
            "invoice_date": t_base,
            "shipment_date": t_ship,
            "payment_date": t_pay,
            "supplier_id": "SUPP-GLOBAL-01",
            "buyer_id": "BUYER-OMEGA-01",
            "supplier_fraud_history": 0,
            "amount_to_supplier_avg_ratio": 0.95
        }
        pred = predict_transaction_risk(sample_feature_data)
        explanation = explain_transaction_risk(sample_feature_data)

        self.assertEqual(pred["risk_level"], "LOW")
        self.assertFalse(pred["is_flagged"])

        # Record risk score in database
        score_id = db.record_risk_score(
            invoice_id=inv_id,
            transaction_id=evt_pay["transaction_id"],
            fraud_probability=pred["fraud_probability"],
            default_probability=pred["default_probability"],
            risk_level=pred["risk_level"],
            model_version=pred["model_version"],
            explanation=explanation["summary_text"],
            top_features=str(explanation["top_factors"])
        )
        self.assertGreater(score_id, 0)

        # 6. Verify Complete Audit Trail
        trail = db.get_invoice_audit_trail(inv_id)
        self.assertEqual(len(trail["transactions"]), 3) # Create, Ship, Pay
        self.assertEqual(len(trail["shipments"]), 1)
        self.assertEqual(len(trail["risk_scores"]), 1)

    def test_complete_fraud_injection_lifecycle(self):
        """Tests fraudulent transaction lifecycle: anomaly detection, high-risk scoring, and flagging."""
        inv_id = "INV-E2E-FRAUD-02"
        supp_wallet = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
        buyer_wallet = "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"
        t_base = datetime.now(timezone.utc) - timedelta(hours=4)

        # 1. InvoiceCreated
        evt_inv = simulator.simulate_invoice_creation(
            invoice_id=inv_id,
            supplier_id="SUPP-SUSP-06",
            buyer_id="BUYER-QUICK-04",
            amount=480000.0,
            item_description="Unverified IP Software Licensing",
            supplier_wallet=supp_wallet,
            buyer_wallet=buyer_wallet,
            created_time=t_base
        )

        # 2. NO Shipment confirmed (Ghost delivery!)

        # 3. Rapid Payment released only 1.2 hours later!
        t_pay = t_base + timedelta(hours=1.2)
        evt_pay = simulator.simulate_payment_release(
            invoice_id=inv_id,
            amount_paid=480000.0,
            buyer_wallet=buyer_wallet,
            supplier_wallet=supp_wallet,
            payment_time=t_pay
        )

        # 4. AI Risk Scoring Engine Analyzes Transaction
        sample_feature_data = {
            "invoice_amount": 480000.0,
            "transaction_amount": 480000.0,
            "carrier": "None",
            "invoice_date": t_base,
            "shipment_date": None,
            "payment_date": t_pay,
            "supplier_id": "SUPP-SUSP-06",
            "buyer_id": "BUYER-QUICK-04",
            "supplier_fraud_history": 6,
            "amount_to_supplier_avg_ratio": 1.7
        }
        pred = predict_transaction_risk(sample_feature_data)
        explanation = explain_transaction_risk(sample_feature_data)

        # 5. Must be HIGH risk and flagged
        self.assertGreaterEqual(pred["fraud_probability"], 0.70)
        self.assertEqual(pred["risk_level"], "HIGH")
        self.assertTrue(pred["is_flagged"])

        # 6. Record in database
        db.record_risk_score(
            invoice_id=inv_id,
            transaction_id=evt_pay["transaction_id"],
            fraud_probability=pred["fraud_probability"],
            default_probability=pred["default_probability"],
            risk_level=pred["risk_level"],
            model_version=pred["model_version"],
            explanation=explanation["summary_text"],
            top_features=str(explanation["top_factors"])
        )

        # 7. Invoice must now be marked FLAGGED_FRAUD in database
        inv_record = db.get_invoice(inv_id)
        self.assertEqual(inv_record["status"], "FLAGGED_FRAUD")

        # 8. Must appear in flagged transactions queue
        flagged = db.get_flagged_transactions()
        flagged_inv_ids = [f["invoice_id"] for f in flagged]
        self.assertIn(inv_id, flagged_inv_ids)


if __name__ == "__main__":
    unittest.main()
