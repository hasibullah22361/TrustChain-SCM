"""
TrustChain SCM - ML & Explainability Test Suite
Tests feature pipeline transformations, XGBoost probability calibration,
threshold categorization, and SHAP TreeExplainer feature attributions.
"""

import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from model.feature_engineering import extract_features_from_dict, load_preprocessor
from model.predict import predict_transaction_risk
from model.explain import explain_transaction_risk


class TestMLPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preprocessor = load_preprocessor()

    def test_01_feature_extraction(self):
        sample = {
            "invoice_amount": 100000.0,
            "transaction_amount": 100000.0,
            "carrier": "DHL Global Express",
            "invoice_date": "2026-09-01T08:00:00Z",
            "shipment_date": "2026-09-03T12:00:00Z",
            "payment_date": "2026-09-20T16:00:00Z",
        }
        df_feat = extract_features_from_dict(sample)
        self.assertEqual(len(df_feat), 1)
        self.assertEqual(df_feat["has_shipment"].iloc[0], 1)
        self.assertAlmostEqual(df_feat["amount_deviation_ratio"].iloc[0], 0.0, places=3)

    def test_02_preprocessor_transformation(self):
        sample = {
            "invoice_amount": 75000.0,
            "transaction_amount": 75000.0,
            "carrier": "FedEx International",
        }
        df_feat = extract_features_from_dict(sample)
        X_trans = self.preprocessor.transform(df_feat)
        self.assertEqual(X_trans.shape[0], 1)
        self.assertGreater(X_trans.shape[1], 15)

    def test_03_clean_transaction_prediction(self):
        clean_sample = {
            "invoice_amount": 125000.0,
            "transaction_amount": 125000.0,
            "supplier_id": "SUPP-GLOBAL-01",
            "buyer_id": "BUYER-OMEGA-01",
            "carrier": "DHL Global Express",
            "invoice_date": "2026-09-01T08:00:00Z",
            "shipment_date": "2026-09-03T12:00:00Z",
            "payment_date": "2026-09-25T14:00:00Z",
            "supplier_fraud_history": 0,
        }
        pred = predict_transaction_risk(clean_sample)
        self.assertIn("fraud_probability", pred)
        self.assertGreaterEqual(pred["fraud_probability"], 0.0)
        self.assertLessEqual(pred["fraud_probability"], 1.0)
        self.assertEqual(pred["risk_level"], "LOW")
        self.assertFalse(pred["is_flagged"])

    def test_04_fraudulent_transaction_prediction(self):
        fraud_sample = {
            "invoice_amount": 450000.0,
            "transaction_amount": 450000.0,
            "supplier_id": "SUPP-SUSP-06",
            "buyer_id": "BUYER-QUICK-04",
            "carrier": "None",
            "invoice_date": "2026-09-08T02:00:00Z",
            "shipment_date": None,
            "payment_date": "2026-09-08T03:30:00Z",  # 1.5 hours later!
            "supplier_fraud_history": 6,
        }
        pred = predict_transaction_risk(fraud_sample)
        self.assertGreater(pred["fraud_probability"], 0.70)
        self.assertEqual(pred["risk_level"], "HIGH")
        self.assertTrue(pred["is_flagged"])

    def test_05_shap_explanation_generation(self):
        fraud_sample = {
            "invoice_amount": 500000.0,
            "transaction_amount": 500000.0,
            "supplier_id": "SUPP-SUSP-06",
            "buyer_id": "BUYER-QUICK-04",
            "carrier": "None",
            "invoice_date": "2026-09-08T02:00:00Z",
            "shipment_date": None,
            "payment_date": "2026-09-08T03:30:00Z",
            "supplier_fraud_history": 6,
        }
        explanation = explain_transaction_risk(fraud_sample)
        self.assertIn("summary_text", explanation)
        self.assertIn("top_factors", explanation)
        self.assertIn("plot_data", explanation)
        self.assertTrue(len(explanation["top_factors"]) > 0)
        # Check that positive factors were found for high-risk transaction
        self.assertGreater(len(explanation["risk_increasers"]), 0)


if __name__ == "__main__":
    unittest.main()
