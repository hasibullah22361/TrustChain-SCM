"""
TrustChain SCM - Feature Engineering Pipeline
Handles transformations, imputations, scaling, and categorical encoding
for both batch training and real-time inference in the dashboard and event listener.
"""

import os
import joblib
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, OneHotEncoder

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "model" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
PREPROCESSOR_PATH = MODELS_DIR / "preprocessor.pkl"

NUMERICAL_FEATURES = [
    "invoice_amount",
    "transaction_amount",
    "amount_deviation_ratio",
    "amount_to_supplier_avg_ratio",
    "time_invoice_to_payment_hours",
    "time_shipment_to_payment_hours",
    "supplier_fraud_history",
    "buyer_fraud_history",
    "supplier_tx_volume",
    "buyer_tx_volume",
    "tx_hour",
]

BINARY_FEATURES = [
    "has_shipment",
    "is_round_amount",
    "is_weekend",
    "is_night_tx",
]

CATEGORICAL_FEATURES = [
    "carrier",
]

ALL_FEATURE_COLS = NUMERICAL_FEATURES + BINARY_FEATURES + CATEGORICAL_FEATURES


def extract_features_from_dict(raw_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Transforms a single transaction event dictionary into the standardized DataFrame format
    required by the preprocessing pipeline.
    """
    inv_amt = float(raw_data.get("invoice_amount", 0.0))
    txn_amt = float(raw_data.get("transaction_amount", inv_amt))

    amount_dev = (txn_amt - inv_amt) / (inv_amt + 1e-5) if inv_amt > 0 else 0.0

    # Timing analysis
    inv_date = raw_data.get("invoice_date")
    ship_date = raw_data.get("shipment_date")
    pay_date = raw_data.get("payment_date")

    time_inv_to_pay = 24.0 * 15.0  # default 15 days
    time_ship_to_pay = 24.0 * 10.0 # default 10 days
    tx_hour = 12
    is_weekend = 0

    if pay_date and inv_date:
        if isinstance(pay_date, str):
            pay_dt = pd.to_datetime(pay_date)
        else:
            pay_dt = pay_date
        if isinstance(inv_date, str):
            inv_dt = pd.to_datetime(inv_date)
        else:
            inv_dt = inv_date

        time_inv_to_pay = max(0.1, (pay_dt - inv_dt).total_seconds() / 3600.0)
        tx_hour = pay_dt.hour
        is_weekend = 1 if pay_dt.weekday() >= 5 else 0

    if pay_date and ship_date:
        if isinstance(pay_date, str):
            pay_dt = pd.to_datetime(pay_date)
        else:
            pay_dt = pay_date
        if isinstance(ship_date, str):
            ship_dt = pd.to_datetime(ship_date)
        else:
            ship_dt = ship_date
        time_ship_to_pay = (pay_dt - ship_dt).total_seconds() / 3600.0
    elif not ship_date:
        time_ship_to_pay = -1.0

    carrier = str(raw_data.get("carrier", "None"))
    has_shipment = 1 if carrier not in ("None", "", "Unregistered Logistics") and ship_date is not None else 0

    row = {
        "invoice_amount": inv_amt,
        "transaction_amount": txn_amt,
        "amount_deviation_ratio": amount_dev,
        "amount_to_supplier_avg_ratio": float(raw_data.get("amount_to_supplier_avg_ratio", 1.0)),
        "time_invoice_to_payment_hours": time_inv_to_pay,
        "time_shipment_to_payment_hours": time_ship_to_pay,
        "supplier_fraud_history": int(raw_data.get("supplier_fraud_history", 0)),
        "buyer_fraud_history": int(raw_data.get("buyer_fraud_history", 0)),
        "supplier_tx_volume": int(raw_data.get("supplier_tx_volume", 25)),
        "buyer_tx_volume": int(raw_data.get("buyer_tx_volume", 25)),
        "tx_hour": tx_hour,
        "has_shipment": has_shipment,
        "is_round_amount": 1 if (txn_amt % 1000 == 0) else 0,
        "is_weekend": is_weekend,
        "is_night_tx": 1 if (tx_hour < 6 or tx_hour > 22) else 0,
        "carrier": carrier,
    }
    return pd.DataFrame([row])


def create_preprocessor() -> ColumnTransformer:
    """Creates a ColumnTransformer pipeline for numerical, binary, and categorical features."""
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", RobustScaler()),
    ])

    bin_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
    ])

    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="None")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_pipeline, NUMERICAL_FEATURES),
            ("bin", bin_pipeline, BINARY_FEATURES),
            ("cat", cat_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop"
    )
    return preprocessor


def fit_and_save_preprocessor(df: pd.DataFrame, target_col: str = "is_fraud") -> Tuple[ColumnTransformer, np.ndarray, np.ndarray]:
    """Fits preprocessor on feature columns, persists to disk, and returns transformed X and y."""
    X = df[ALL_FEATURE_COLS]
    y = df[target_col].values if target_col in df.columns else None

    preprocessor = create_preprocessor()
    X_transformed = preprocessor.fit_transform(X)

    joblib.dump(preprocessor, PREPROCESSOR_PATH)
    print(f"Fitted feature preprocessor saved to: {PREPROCESSOR_PATH}")
    print(f"Transformed feature dimension: {X_transformed.shape}")
    return preprocessor, X_transformed, y


def load_preprocessor() -> ColumnTransformer:
    """Loads the serialized preprocessor from disk."""
    if not PREPROCESSOR_PATH.exists():
        raise FileNotFoundError(f"Preprocessor not found at {PREPROCESSOR_PATH}. Train the model first.")
    return joblib.load(PREPROCESSOR_PATH)


if __name__ == "__main__":
    csv_path = BASE_DIR / "data" / "raw" / "supply_chain_transactions.csv"
    if csv_path.exists():
        data = pd.read_csv(csv_path)
        prep, X_t, y = fit_and_save_preprocessor(data)
        print("Feature engineering pipeline verification passed.")
    else:
        print("Raw dataset not found. Run generate_data.py first.")
