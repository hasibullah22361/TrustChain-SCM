"""
TrustChain SCM - Model Training & Evaluation
Trains a Scikit-Learn baseline (RandomForest) and Advanced XGBoost Classifier
with class-imbalance weighting (scale_pos_weight), stratifying train/test splits,
and computing rigorous fraud-minority-class metrics (Precision, Recall, F1, ROC-AUC).
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from model.feature_engineering import (
    ALL_FEATURE_COLS,
    create_preprocessor,
    PREPROCESSOR_PATH,
    MODELS_DIR,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "raw" / "supply_chain_transactions.csv"
MODEL_PATH = MODELS_DIR / "fraud_model.pkl"
METRICS_PATH = MODELS_DIR / "metrics.json"


def train_and_evaluate_models() -> Dict[str, Any]:
    """Trains baseline and XGBoost models, logs metrics, and serializes best weights."""
    print("==========================================================")
    print("TrustChain SCM - AI/ML Risk Scoring Model Training")
    print("==========================================================")

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}. Run generate_data.py first.")

    df = pd.read_csv(DATA_PATH)
    X = df[ALL_FEATURE_COLS]
    y = df["is_fraud"].values

    # Stratified split to preserve fraud minority class ratio (8.5%)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"Training set samples:   {len(X_train)} (Fraud cases: {sum(y_train)})")
    print(f"Test set samples:       {len(X_test)} (Fraud cases: {sum(y_test)})")

    # Fit preprocessor on training data only to strictly prevent data leakage
    preprocessor = create_preprocessor()
    X_train_transformed = preprocessor.fit_transform(X_train)
    X_test_transformed = preprocessor.transform(X_test)

    joblib.dump(preprocessor, PREPROCESSOR_PATH)
    print(f"Saved fitted preprocessor to: {PREPROCESSOR_PATH}")

    # Calculate scale_pos_weight for XGBoost: negative_count / positive_count
    neg_count = len(y_train) - sum(y_train)
    pos_count = sum(y_train)
    scale_pos_weight = neg_count / max(1, pos_count)
    print(f"Class imbalance ratio (scale_pos_weight): {scale_pos_weight:.2f}")

    # 1. Baseline Model: Random Forest
    print("\n--- Training Baseline Model: Random Forest ---")
    baseline_rf = RandomForestClassifier(
        n_estimators=120,
        max_depth=10,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    baseline_rf.fit(X_train_transformed, y_train)
    rf_preds = baseline_rf.predict(X_test_transformed)
    rf_probs = baseline_rf.predict_proba(X_test_transformed)[:, 1]

    rf_metrics = {
        "precision_fraud": float(precision_score(y_test, rf_preds)),
        "recall_fraud": float(recall_score(y_test, rf_preds)),
        "f1_fraud": float(f1_score(y_test, rf_preds)),
        "roc_auc": float(roc_auc_score(y_test, rf_probs)),
        "pr_auc": float(average_precision_score(y_test, rf_probs)),
    }
    print(f"Baseline RF -> Fraud Recall: {rf_metrics['recall_fraud']:.2%}, Precision: {rf_metrics['precision_fraud']:.2%}, ROC-AUC: {rf_metrics['roc_auc']:.4f}")

    # 2. Advanced Model: XGBoost Classifier
    print("\n--- Training Advanced Model: XGBoost Classifier ---")
    xgb_model = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=scale_pos_weight,
        subsample=0.85,
        colsample_bytree=0.85,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1
    )
    xgb_model.fit(X_train_transformed, y_train)
    xgb_preds = xgb_model.predict(X_test_transformed)
    xgb_probs = xgb_model.predict_proba(X_test_transformed)[:, 1]

    cm = confusion_matrix(y_test, xgb_preds).tolist()
    cr = classification_report(y_test, xgb_preds, output_dict=True)

    xgb_metrics = {
        "model_name": "XGBoost Classifier (Class Balanced)",
        "model_version": "v1.2.0-xgb",
        "precision_fraud": float(precision_score(y_test, xgb_preds)),
        "recall_fraud": float(recall_score(y_test, xgb_preds)),
        "f1_fraud": float(f1_score(y_test, xgb_preds)),
        "roc_auc": float(roc_auc_score(y_test, xgb_probs)),
        "pr_auc": float(average_precision_score(y_test, xgb_probs)),
        "confusion_matrix": cm,
        "classification_report": cr,
        "scale_pos_weight": float(scale_pos_weight),
        "test_samples": len(y_test),
        "fraud_test_samples": int(sum(y_test)),
    }

    print("\n================ Classification Report (XGBoost) ================")
    print(classification_report(y_test, xgb_preds, target_names=["Normal (0)", "Fraud (1)"]))
    print(f"Confusion Matrix:\n{np.array(cm)}")
    print(f"ROC-AUC: {xgb_metrics['roc_auc']:.4f} | PR-AUC: {xgb_metrics['pr_auc']:.4f}")
    print(f"Fraud F1-Score: {xgb_metrics['f1_fraud']:.4f}")

    # Save the superior XGBoost model
    joblib.dump(xgb_model, MODEL_PATH)
    print(f"\nTrained model successfully persisted to: {MODEL_PATH}")

    # Save comparative metrics
    all_metrics = {
        "baseline_rf": rf_metrics,
        "advanced_xgboost": xgb_metrics,
        "trained_at": pd.Timestamp.now().isoformat(),
    }
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)
    print(f"Metrics saved to: {METRICS_PATH}")

    return all_metrics


if __name__ == "__main__":
    train_and_evaluate_models()
