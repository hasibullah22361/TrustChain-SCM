"""
TrustChain SCM - Blockchain Event Simulator (Demo Mode)
Generates cryptographically valid block headers, transaction hashes, and event logs
for seamless presentation when Sepolia or external RPC networks are unavailable.
"""

import os
import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from database.database import db

logger = logging.getLogger("trustchain.simulator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def generate_tx_hash(seed_str: str) -> str:
    """Generates a pseudo-deterministic 66-character Ethereum transaction hash."""
    hasher = hashlib.sha256()
    hasher.update(seed_str.encode("utf-8"))
    hasher.update(str(time.time_ns()).encode("utf-8"))
    return "0x" + hasher.hexdigest()


class BlockchainSimulator:
    """Simulates an on-chain ledger generating blocks and events directly into the database."""

    def __init__(self, current_block: int = 18452000):
        self.current_block = current_block

    def simulate_invoice_creation(
        self,
        invoice_id: str,
        supplier_id: str,
        buyer_id: str,
        amount: float,
        item_description: str,
        supplier_wallet: str,
        buyer_wallet: str,
        due_days: int = 45,
        created_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Simulates an on-chain InvoiceCreated event."""
        self.current_block += 1
        ts = created_time or datetime.now(timezone.utc)
        due_date = ts + timedelta(days=due_days)
        tx_hash = generate_tx_hash(f"{invoice_id}_CREATE_{self.current_block}")

        # Ensure party records exist
        db.record_party(supplier_id, f"Supplier {supplier_id}", "SUPPLIER", supplier_wallet)
        db.record_party(buyer_id, f"Buyer {buyer_id}", "BUYER", buyer_wallet)

        # Record invoice in database
        db.record_invoice(
            invoice_id=invoice_id,
            supplier_id=supplier_id,
            buyer_id=buyer_id,
            amount=amount,
            currency="USD",
            item_description=item_description,
            invoice_date=ts,
            due_date=due_date,
            status="CREATED",
            blockchain_tx_hash=tx_hash,
            block_number=self.current_block
        )

        # Record transaction event
        tx_id = f"TXN-{invoice_id}-CRE"
        db.record_transaction(
            transaction_id=tx_id,
            invoice_id=invoice_id,
            transaction_type="INVOICE_CREATED",
            amount=amount,
            timestamp=ts,
            blockchain_tx_hash=tx_hash,
            sender_address=supplier_wallet,
            receiver_address=buyer_wallet,
            block_number=self.current_block
        )

        logger.info(f"[SIMULATOR] InvoiceCreated event emitted on block #{self.current_block}: {invoice_id} ({tx_hash[:10]}...)")
        return {
            "invoice_id": invoice_id,
            "block_number": self.current_block,
            "tx_hash": tx_hash,
            "timestamp": ts.isoformat(),
            "status": "CREATED"
        }

    def simulate_shipment_confirmation(
        self,
        invoice_id: str,
        carrier: str,
        tracking_number: str,
        supplier_wallet: str,
        shipment_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Simulates an on-chain ShipmentConfirmed event."""
        self.current_block += 1
        ts = shipment_time or datetime.now(timezone.utc)
        tx_hash = generate_tx_hash(f"{invoice_id}_SHIP_{self.current_block}")
        shipment_id = f"SHIP-{invoice_id}"

        # Record shipment
        db.record_shipment(
            shipment_id=shipment_id,
            invoice_id=invoice_id,
            carrier=carrier,
            tracking_number=tracking_number,
            shipment_date=ts,
            status="DELIVERED",
            blockchain_tx_hash=tx_hash,
            block_number=self.current_block
        )

        # Record transaction event
        tx_id = f"TXN-{invoice_id}-SHP"
        db.record_transaction(
            transaction_id=tx_id,
            invoice_id=invoice_id,
            transaction_type="SHIPMENT_CONFIRMED",
            amount=0.0,
            timestamp=ts,
            blockchain_tx_hash=tx_hash,
            sender_address=supplier_wallet,
            receiver_address="0x0000000000000000000000000000000000000000",
            block_number=self.current_block
        )

        logger.info(f"[SIMULATOR] ShipmentConfirmed event on block #{self.current_block}: {invoice_id} via {carrier}")
        return {
            "invoice_id": invoice_id,
            "shipment_id": shipment_id,
            "block_number": self.current_block,
            "tx_hash": tx_hash,
            "status": "SHIPMENT_CONFIRMED"
        }

    def simulate_payment_release(
        self,
        invoice_id: str,
        amount_paid: float,
        buyer_wallet: str,
        supplier_wallet: str,
        payment_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Simulates an on-chain PaymentReleased event."""
        self.current_block += 1
        ts = payment_time or datetime.now(timezone.utc)
        tx_hash = generate_tx_hash(f"{invoice_id}_PAY_{self.current_block}")

        # Record transaction event
        tx_id = f"TXN-{invoice_id}-PAY"
        db.record_transaction(
            transaction_id=tx_id,
            invoice_id=invoice_id,
            transaction_type="PAYMENT_RELEASED",
            amount=amount_paid,
            timestamp=ts,
            blockchain_tx_hash=tx_hash,
            sender_address=buyer_wallet,
            receiver_address=supplier_wallet,
            block_number=self.current_block
        )

        # Update invoice status in database
        inv = db.get_invoice(invoice_id)
        if inv and inv["status"] != "FLAGGED_FRAUD":
            db.record_invoice(
                invoice_id=invoice_id,
                supplier_id=inv["supplier_id"],
                buyer_id=inv["buyer_id"],
                amount=inv["amount"],
                currency=inv["currency"],
                item_description=inv["item_description"],
                invoice_date=inv["invoice_date"],
                due_date=inv["due_date"],
                status="PAID",
                blockchain_tx_hash=tx_hash,
                block_number=self.current_block
            )

        logger.info(f"[SIMULATOR] PaymentReleased event on block #{self.current_block}: {invoice_id} amount: ${amount_paid:,.2f}")
        return {
            "invoice_id": invoice_id,
            "transaction_id": tx_id,
            "amount_paid": amount_paid,
            "block_number": self.current_block,
            "tx_hash": tx_hash,
            "status": "PAID"
        }


simulator = BlockchainSimulator()

if __name__ == "__main__":
    test_res = simulator.simulate_invoice_creation(
        invoice_id="INV-SIM-TEST-99",
        supplier_id="SUPP-GLOBAL-01",
        buyer_id="BUYER-OMEGA-01",
        amount=142000.00,
        item_description="Precision Aviation Hydraulics",
        supplier_wallet="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        buyer_wallet="0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"
    )
    print("Simulated Event Result:", test_res)
