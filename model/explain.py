"""
TrustChain SCM - SHAP Explainability Engine
Leverages shap.TreeExplainer to produce mathematically rigorous local feature attributions
explaining why individual supply-chain transactions were flagged or cleared.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Union
import numpy as np
import pandas as pd
import shap

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from model.feature_engineering import extract_features_from_dict, ALL_FEATURE_COLS
from model.predict import get_model_and_preprocessor, predict_transaction_risk

_cached_explainer = None


def get_tree_explainer():
    """Initializes and caches shap.TreeExplainer for the XGBoost model."""
    global _cached_explainer
    if _cached_explainer is None:
        model, _ = get_model_and_preprocessor()
        _cached_explainer = shap.TreeExplainer(model)
    return _cached_explainer


HUMAN_FEATURE_NAMES = {
    "num__time_invoice_to_payment_hours": "Invoice-to-Payment Time Interval",
    "num__time_shipment_to_payment_hours": "Shipment-to-Payment Time Interval",
    "num__amount_deviation_ratio": "Transaction vs Invoice Amount Deviation",
    "num__amount_to_supplier_avg_ratio": "Amount Ratio vs Supplier Average",
    "num__supplier_fraud_history": "Supplier Prior Fraud Incidents",
    "num__buyer_fraud_history": "Buyer Prior Fraud Incidents",
    "num__invoice_amount": "Total Invoice Face Value",
    "num__transaction_amount": "Settlement Transaction Amount",
    "num__tx_hour": "Transaction Hour of Day",
    "num__supplier_tx_volume": "Supplier Historical Trade Volume",
    "num__buyer_tx_volume": "Buyer Historical Trade Volume",
    "bin__has_shipment": "Physical Logistics Verification (Carrier Delivery)",
    "bin__is_round_amount": "Large Clean Round Dollar Amount",
    "bin__is_night_tx": "Off-Hours Non-Business Timing (00:00 - 05:00)",
    "bin__is_weekend": "Weekend Transaction Processing",
    "cat__carrier_None": "Unregistered / Missing Carrier (Ghost Delivery)",
}


def explain_transaction_risk(transaction_data: Union[Dict[str, Any], pd.DataFrame]) -> Dict[str, Any]:
    """
    Computes SHAP feature contributions for a single transaction.
    Returns:
      - fraud_probability, risk_level, is_flagged
      - top_positive_factors (factors increasing risk)
      - top_negative_factors (factors mitigating risk)
      - summary_text (multi-line auditor-ready explanation)
      - feature_importance_plot_data (dict for Plotly rendering)
    """
    model, preprocessor = get_model_and_preprocessor()
    explainer = get_tree_explainer()

    if isinstance(transaction_data, dict):
        raw_dict = transaction_data
        df_feat = extract_features_from_dict(raw_dict)
    elif isinstance(transaction_data, pd.DataFrame):
        df_feat = transaction_data
        raw_dict = transaction_data.iloc[0].to_dict()
    else:
        raise ValueError("transaction_data must be dict or DataFrame")

    # Run prediction
    pred = predict_transaction_risk(df_feat)
    fraud_prob = pred["fraud_probability"]
    risk_level = pred["risk_level"]

    # Transform features
    X_transformed = preprocessor.transform(df_feat)
    feature_names = preprocessor.get_feature_names_out()

    # Compute SHAP values
    shap_raw = explainer.shap_values(X_transformed)
    if isinstance(shap_raw, list):
        # Multi-class or binary list
        shap_vals = shap_raw[1][0] if len(shap_raw) > 1 else shap_raw[0][0]
    elif len(shap_raw.shape) == 2:
        shap_vals = shap_raw[0]
    else:
        shap_vals = shap_raw

    # Pair features with their SHAP impact
    feature_contributions = []
    for f_name, s_val in zip(feature_names, shap_vals):
        clean_label = HUMAN_FEATURE_NAMES.get(f_name, f_name.replace("num__", "").replace("bin__", "").replace("cat__", ""))
        feature_contributions.append({
            "feature_raw": f_name,
            "feature_label": clean_label,
            "shap_value": float(s_val),
            "abs_impact": abs(float(s_val))
        })

    # Sort by absolute impact
    feature_contributions.sort(key=lambda x: x["abs_impact"], reverse=True)

    # Separate top risk increasers and reducers
    risk_increasers = [f for f in feature_contributions if f["shap_value"] > 0.01][:5]
    risk_reducers = [f for f in feature_contributions if f["shap_value"] < -0.01][:5]

    # Generate professional auditor narrative
    lines = [f"Risk Score: {fraud_prob:.1%} ({risk_level} RISK)"]
    if risk_level == "HIGH":
        lines.append("\nPrimary Anomaly Drivers (Positive SHAP Contribution):")
        for f in risk_increasers:
            lines.append(f"  + {f['feature_label']} (+{f['shap_value']:.2f})")
    elif risk_level == "LOW":
        lines.append("\nPrimary Trust Drivers (Negative SHAP Contribution):")
        for f in risk_reducers:
            lines.append(f"  - {f['feature_label']} ({f['shap_value']:.2f})")
    else:
        lines.append("\nBalanced Risk Drivers:")
        for f in feature_contributions[:4]:
            sign = "+" if f["shap_value"] >= 0 else "-"
            lines.append(f"  {sign} {f['feature_label']} ({f['shap_value']:+.2f})")

    summary_text = "\n".join(lines)

    # Plot data for Plotly horizontal bar chart
    top_display = feature_contributions[:8]
    plot_data = {
        "features": [f["feature_label"] for f in reversed(top_display)],
        "shap_values": [f["shap_value"] for f in reversed(top_display)],
        "colors": ["#EF4444" if f["shap_value"] > 0 else "#10B981" for f in reversed(top_display)]
    }

    return {
        "fraud_probability": fraud_prob,
        "default_probability": pred["default_probability"],
        "risk_level": risk_level,
        "is_flagged": pred["is_flagged"],
        "action_label": pred["action_label"],
        "summary_text": summary_text,
        "top_factors": {f["feature_label"]: round(f["shap_value"], 3) for f in top_display},
        "risk_increasers": risk_increasers,
        "risk_reducers": risk_reducers,
        "plot_data": plot_data,
    }


if __name__ == "__main__":
    suspicious_case = {
        "invoice_amount": 450000.0,
        "transaction_amount": 450000.0,
        "supplier_id": "SUPP-SUSP-06",
        "buyer_id": "BUYER-QUICK-04",
        "carrier": "None",
        "invoice_date": "2026-09-08T02:11:00Z",
        "shipment_date": None,
        "payment_date": "2026-09-08T04:15:00Z",
        "supplier_fraud_history": 6,
        "amount_to_supplier_avg_ratio": 1.6
    }
    exp = explain_transaction_risk(suspicious_case)
    print("\n--- SHAP EXPLANATION DEMO ---")
    print(exp["summary_text"])
    print("\nTop Contributing Factors:", exp["top_factors"])
