"""
TrustChain SCM - Synthetic Supply Chain Transaction Dataset Generator
Generates realistic supply chain trade receivables, logistics events, and settlement records
with documented fraud injection patterns (Minority Class ~8.5%).
"""

import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

# Set deterministic random seeds for reproducible data science
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV = DATA_DIR / "supply_chain_transactions.csv"

# Pre-defined counterparties with baseline risk profiles
SUPPLIERS = [
    {"id": "SUPP-GLOBAL-01", "name": "AeroTech Components Ltd", "risk_tier": "LOW", "hist_fraud": 0, "avg_amt": 120000},
    {"id": "SUPP-NEXUS-02",  "name": "Apex Precision Sensors",  "risk_tier": "LOW", "hist_fraud": 0, "avg_amt": 85000},
    {"id": "SUPP-TITAN-03",  "name": "Titan Raw Materials Corp","risk_tier": "MED", "hist_fraud": 1, "avg_amt": 280000},
    {"id": "SUPP-PREC-04",   "name": "Precision Optics Europe",  "risk_tier": "LOW", "hist_fraud": 0, "avg_amt": 95000},
    {"id": "SUPP-IND-05",    "name": "Indus Microchips Corp",   "risk_tier": "MED", "hist_fraud": 1, "avg_amt": 160000},
    {"id": "SUPP-SUSP-06",   "name": "ShadowShell Holdings Inc", "risk_tier": "HIGH","hist_fraud": 6, "avg_amt": 390000},
    {"id": "SUPP-PHANTOM-07","name": "Vanguard Trade Ltd",       "risk_tier": "HIGH","hist_fraud": 8, "avg_amt": 450000},
    {"id": "SUPP-PACIFIC-08","name": "Pacific Freight Logistics","risk_tier": "LOW", "hist_fraud": 0, "avg_amt": 75000},
]

BUYERS = [
    {"id": "BUYER-OMEGA-01", "name": "Omega Automotive Group",  "risk_tier": "LOW", "hist_fraud": 0},
    {"id": "BUYER-VORTEX-02","name": "Vortex Aerospace Inc",   "risk_tier": "LOW", "hist_fraud": 0},
    {"id": "BUYER-STEEL-03", "name": "Continental Heavy Metals","risk_tier": "MED", "hist_fraud": 1},
    {"id": "BUYER-QUICK-04", "name": "FlashRetail Logistics",   "risk_tier": "HIGH","hist_fraud": 5},
    {"id": "BUYER-GLOBAL-05","name": "Global Pharma Systems",   "risk_tier": "LOW", "hist_fraud": 0},
    {"id": "BUYER-APEX-06",  "name": "Apex EV Powertrains",     "risk_tier": "LOW", "hist_fraud": 0},
]

CARRIERS = ["DHL Global Express", "FedEx International", "Maersk Ocean Freight", "Kuehne+Nagel Logistics", "DB Schenker", "None"]


def generate_synthetic_dataset(n_samples: int = 6000, target_fraud_rate: float = 0.085) -> pd.DataFrame:
    """
    Generates a realistic tabular supply-chain transaction dataset.
    Normal cases: realistic logistics lead-time, standard settlement intervals (15-60 days), valid shipping.
    Fraudulent cases:
      1. AMOUNT_INFLATION: Transaction amount significantly higher than invoice or historical average.
      2. RAPID_GHOST_SETTLEMENT: Payment released within hours before physical dispatch (no carrier).
      3. OFF_HOURS_ROUND_SUM: Exact round amounts issued at odd hours (00:00 - 04:00) by high-risk parties.
      4. SERIAL_COUNTERPARTY_SPIKE: High counterparty historical fraud combined with excessive volume.
    """
    records = []
    base_start_time = datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)

    n_fraud = int(n_samples * target_fraud_rate)
    n_normal = n_samples - n_fraud

    labels = [0] * n_normal + [1] * n_fraud
    random.shuffle(labels)

    supplier_counts = {s["id"]: 0 for s in SUPPLIERS}
    buyer_counts = {b["id"]: 0 for b in BUYERS}

    for idx, is_fraud in enumerate(labels):
        invoice_id = f"INV-SYN-{10000 + idx}"
        txn_id = f"TXN-SYN-{10000 + idx}"

        # Assign counterparty
        if is_fraud:
            # Fraudulent transactions more frequently originate from high-risk or compromised parties
            high_risk_supps = [s for s in SUPPLIERS if s["risk_tier"] in ("MED", "HIGH")]
            supp = random.choice(high_risk_supps) if random.random() < 0.75 else random.choice(SUPPLIERS)
            high_risk_buyers = [b for b in BUYERS if b["risk_tier"] in ("MED", "HIGH")]
            buyer = random.choice(high_risk_buyers) if random.random() < 0.65 else random.choice(BUYERS)
        else:
            low_risk_supps = [s for s in SUPPLIERS if s["risk_tier"] in ("LOW", "MED")]
            supp = random.choice(low_risk_supps)
            buyer = random.choice([b for b in BUYERS if b["risk_tier"] == "LOW"] or BUYERS)

        supplier_counts[supp["id"]] += 1
        buyer_counts[buyer["id"]] += 1

        # Base timestamp across a 18-month window
        time_offset_days = random.uniform(0, 540)
        inv_datetime = base_start_time + timedelta(days=time_offset_days)

        # Baseline amount based on supplier average
        base_amt = max(5000.0, np.random.normal(supp["avg_amt"], supp["avg_amt"] * 0.25))

        if not is_fraud:
            # NORMAL TRANSACTION DYNAMICS
            invoice_amount = round(base_amt, 2)
            # Small variance in final payment (discounts, FX differences, minor deductions)
            variance = random.uniform(-0.02, 0.01)
            transaction_amount = round(invoice_amount * (1.0 + variance), 2)

            # Logistics transit: 2 to 10 days
            shipment_delay_days = random.uniform(1.5, 8.0)
            ship_datetime = inv_datetime + timedelta(days=shipment_delay_days)
            carrier = random.choice(CARRIERS[:-1])  # Has valid carrier

            # Payment delay: standard Net-30 or Net-45 terms (15 to 45 days after invoice)
            payment_delay_days = shipment_delay_days + random.uniform(10.0, 35.0)
            pay_datetime = inv_datetime + timedelta(days=payment_delay_days)

            is_round = 1 if (transaction_amount % 1000 == 0) else 0
            fraud_type = "NORMAL"

        else:
            # FRAUDULENT TRANSACTION INJECTION
            fraud_mechanism = random.choice([
                "AMOUNT_INFLATION",
                "RAPID_GHOST_SETTLEMENT",
                "OFF_HOURS_ROUND_SUM",
                "SERIAL_COUNTERPARTY_SPIKE"
            ])
            fraud_type = fraud_mechanism

            if fraud_mechanism == "AMOUNT_INFLATION":
                # Inflated invoice or settlement amount far exceeding normal baseline
                invoice_amount = round(base_amt, 2)
                multiplier = random.uniform(1.35, 2.50)
                transaction_amount = round(invoice_amount * multiplier, 2)
                shipment_delay_days = random.uniform(2.0, 6.0)
                ship_datetime = inv_datetime + timedelta(days=shipment_delay_days)
                carrier = random.choice(CARRIERS[:-1])
                payment_delay_days = shipment_delay_days + random.uniform(5.0, 20.0)
                pay_datetime = inv_datetime + timedelta(days=payment_delay_days)
                is_round = 0

            elif fraud_mechanism == "RAPID_GHOST_SETTLEMENT":
                # Ghost shipment: payment released within 1 - 6 hours with NO valid carrier
                invoice_amount = round(base_amt * random.uniform(1.1, 1.8), 2)
                transaction_amount = invoice_amount
                carrier = "None"
                shipment_delay_days = 0.0
                ship_datetime = None
                # Payment released in hours!
                pay_delay_hours = random.uniform(0.5, 5.0)
                payment_delay_days = pay_delay_hours / 24.0
                pay_datetime = inv_datetime + timedelta(hours=pay_delay_hours)
                is_round = 0

            elif fraud_mechanism == "OFF_HOURS_ROUND_SUM":
                # Clean round numbers ($250,000, $500,000) generated in late night hours
                clean_rounds = [100000.0, 250000.0, 300000.0, 450000.0, 500000.0, 750000.0]
                invoice_amount = random.choice(clean_rounds)
                transaction_amount = invoice_amount
                # Set payment hour to midnight - 4am
                night_hour = random.randint(0, 4)
                night_minute = random.randint(0, 59)
                shipment_delay_days = random.uniform(0.5, 2.0)
                carrier = random.choice(["None", "Unregistered Logistics"])
                ship_datetime = inv_datetime + timedelta(days=shipment_delay_days)
                pay_datetime = (inv_datetime + timedelta(days=random.uniform(1.0, 4.0))).replace(
                    hour=night_hour, minute=night_minute
                )
                payment_delay_days = (pay_datetime - inv_datetime).total_seconds() / 86400.0
                is_round = 1

            else:  # SERIAL_COUNTERPARTY_SPIKE
                invoice_amount = round(base_amt * random.uniform(1.5, 2.2), 2)
                transaction_amount = round(invoice_amount * 1.15, 2)
                carrier = random.choice(CARRIERS)
                shipment_delay_days = random.uniform(1.0, 5.0)
                ship_datetime = inv_datetime + timedelta(days=shipment_delay_days)
                payment_delay_days = random.uniform(3.0, 10.0)
                pay_datetime = inv_datetime + timedelta(days=payment_delay_days)
                is_round = 1 if (transaction_amount % 1000 == 0) else 0

        # Derived timing deltas
        time_inv_to_pay_hours = (pay_datetime - inv_datetime).total_seconds() / 3600.0
        time_ship_to_pay_hours = (
            (pay_datetime - ship_datetime).total_seconds() / 3600.0 if ship_datetime else -1.0
        )
        amount_deviation_ratio = (transaction_amount - invoice_amount) / (invoice_amount + 1e-5)
        amount_to_supp_avg = transaction_amount / (supp["avg_amt"] + 1e-5)

        tx_hour = pay_datetime.hour
        is_weekend = 1 if pay_datetime.weekday() >= 5 else 0

        record = {
            "invoice_id": invoice_id,
            "transaction_id": txn_id,
            "supplier_id": supp["id"],
            "buyer_id": buyer["id"],
            "carrier": carrier,
            "has_shipment": 1 if carrier != "None" and ship_datetime is not None else 0,
            "invoice_amount": invoice_amount,
            "transaction_amount": transaction_amount,
            "amount_deviation_ratio": round(amount_deviation_ratio, 4),
            "amount_to_supplier_avg_ratio": round(amount_to_supp_avg, 4),
            "time_invoice_to_payment_hours": round(time_inv_to_pay_hours, 2),
            "time_shipment_to_payment_hours": round(time_ship_to_pay_hours, 2),
            "supplier_fraud_history": supp["hist_fraud"],
            "buyer_fraud_history": buyer["hist_fraud"],
            "supplier_tx_volume": supplier_counts[supp["id"]],
            "buyer_tx_volume": buyer_counts[buyer["id"]],
            "is_round_amount": is_round,
            "tx_hour": tx_hour,
            "is_weekend": is_weekend,
            "is_night_tx": 1 if (tx_hour < 6 or tx_hour > 22) else 0,
            "fraud_type": fraud_type,
            "is_fraud": is_fraud,  # Target variable (0 = Normal, 1 = Fraud)
        }
        records.append(record)

    df = pd.DataFrame(records)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Generated {len(df)} synthetic transactions.")
    print(f"Fraud distribution:\n{df['is_fraud'].value_counts(normalize=True).mul(100).round(2)}%")
    print(f"Saved dataset to: {OUTPUT_CSV}")
    return df


if __name__ == "__main__":
    generate_synthetic_dataset(n_samples=6000, target_fraud_rate=0.085)
