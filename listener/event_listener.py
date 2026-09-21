"""
TrustChain SCM - Real-Time Blockchain Event Listener
Listens to on-chain events via web3.py (InvoiceCreated, ShipmentConfirmed, PaymentReleased),
normalizes transaction payloads, persists them to SQL, deduplicates by tx_hash,
and triggers real-time AI risk evaluation.
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from web3 import Web3
from dotenv import load_dotenv

from database.database import db
from listener.blockchain_config import get_web3_connection, get_contract_instance, CONTRACT_ADDRESS, RPC_URL

load_dotenv()

logger = logging.getLogger("trustchain.listener")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class BlockchainEventListener:
    """Monitors live blockchain events and synchronizes them into the SQL relational store."""

    def __init__(self, rpc_url: Optional[str] = None, contract_addr: Optional[str] = None):
        self.rpc_url = rpc_url or RPC_URL
        self.contract_addr = contract_addr or CONTRACT_ADDRESS
        self.w3 = None
        self.contract = None
        self.is_connected = False
        self.last_checked_block = 0
        self.connect()

    def connect(self) -> bool:
        """Establishes or refreshes Web3 connection and contract handle."""
        self.w3, self.is_connected = get_web3_connection(self.rpc_url)
        if self.is_connected:
            self.contract = get_contract_instance(self.w3, self.contract_addr)
            try:
                self.last_checked_block = max(0, self.w3.eth.block_number - 100)
                logger.info(f"Listener initialized from block #{self.last_checked_block}")
            except Exception as ex:
                logger.warning(f"Could not fetch current block: {ex}")
                self.last_checked_block = 0
        else:
            logger.info("Live network unreachable. Operating listener in fallback polling mode.")
        return self.is_connected

    def process_invoice_created_event(self, event_args: Dict[str, Any], tx_hash: str, block_num: int):
        """Extracts and stores InvoiceCreated event into SQL."""
        inv_id = str(event_args.get("invoiceId"))
        supplier = str(event_args.get("supplier"))
        buyer = str(event_args.get("buyer"))
        amount = float(event_args.get("amount", 0)) / 1e18 if event_args.get("amount", 0) > 1e15 else float(event_args.get("amount", 0))
        due_ts = int(event_args.get("dueDate", time.time() + 86400 * 30))
        item_desc = str(event_args.get("itemDescription", "Commercial Goods"))
        created_ts = datetime.fromtimestamp(event_args.get("timestamp", time.time()), timezone.utc)
        due_date = datetime.fromtimestamp(due_ts, timezone.utc)

        # Upsert parties
        db.record_party(supplier, f"Party {supplier[:8]}", "SUPPLIER", supplier)
        db.record_party(buyer, f"Party {buyer[:8]}", "BUYER", buyer)

        # Record invoice
        db.record_invoice(
            invoice_id=inv_id,
            supplier_id=supplier,
            buyer_id=buyer,
            amount=amount,
            currency="USD",
            item_description=item_desc,
            invoice_date=created_ts,
            due_date=due_date,
            status="CREATED",
            blockchain_tx_hash=tx_hash,
            block_number=block_num
        )

        # Record transaction event
        tx_id = f"TXN-{inv_id}-CRE"
        db.record_transaction(
            transaction_id=tx_id,
            invoice_id=inv_id,
            transaction_type="INVOICE_CREATED",
            amount=amount,
            timestamp=created_ts,
            blockchain_tx_hash=tx_hash,
            sender_address=supplier,
            receiver_address=buyer,
            block_number=block_num
        )
        logger.info(f"Ingested InvoiceCreated event into SQL: {inv_id} (tx: {tx_hash[:10]}...)")

    def process_shipment_confirmed_event(self, event_args: Dict[str, Any], tx_hash: str, block_num: int):
        """Extracts and stores ShipmentConfirmed event into SQL."""
        inv_id = str(event_args.get("invoiceId"))
        carrier = str(event_args.get("carrier", "Standard Logistics"))
        tracking = str(event_args.get("trackingNumber", "TRK-000000"))
        ts = datetime.fromtimestamp(event_args.get("timestamp", time.time()), timezone.utc)

        ship_id = f"SHIP-{inv_id}"
        db.record_shipment(
            shipment_id=ship_id,
            invoice_id=inv_id,
            carrier=carrier,
            tracking_number=tracking,
            shipment_date=ts,
            status="IN_TRANSIT",
            blockchain_tx_hash=tx_hash,
            block_number=block_num
        )

        tx_id = f"TXN-{inv_id}-SHP"
        db.record_transaction(
            transaction_id=tx_id,
            invoice_id=inv_id,
            transaction_type="SHIPMENT_CONFIRMED",
            amount=0.0,
            timestamp=ts,
            blockchain_tx_hash=tx_hash,
            block_number=block_num
        )
        logger.info(f"Ingested ShipmentConfirmed event into SQL: {inv_id} via {carrier}")

    def process_payment_released_event(self, event_args: Dict[str, Any], tx_hash: str, block_num: int):
        """Extracts and stores PaymentReleased event into SQL."""
        inv_id = str(event_args.get("invoiceId"))
        buyer = str(event_args.get("buyer"))
        amt = float(event_args.get("amountPaid", 0)) / 1e18 if event_args.get("amountPaid", 0) > 1e15 else float(event_args.get("amountPaid", 0))
        ts = datetime.fromtimestamp(event_args.get("timestamp", time.time()), timezone.utc)

        tx_id = f"TXN-{inv_id}-PAY"
        db.record_transaction(
            transaction_id=tx_id,
            invoice_id=inv_id,
            transaction_type="PAYMENT_RELEASED",
            amount=amt,
            timestamp=ts,
            blockchain_tx_hash=tx_hash,
            sender_address=buyer,
            block_number=block_num
        )

        # Trigger AI Model evaluation for the settlement event
        self._trigger_ai_risk_scoring(inv_id, tx_id, amt, ts)
        logger.info(f"Ingested PaymentReleased event into SQL: {inv_id} for ${amt:,.2f}")

    def _trigger_ai_risk_scoring(self, invoice_id: str, transaction_id: str, amount: float, timestamp: datetime):
        """Invokes the AI prediction pipeline to score the newly processed transaction."""
        try:
            from model.predict import predict_transaction_risk
            from model.explain import explain_transaction_risk

            inv = db.get_invoice(invoice_id)
            if not inv:
                return

            trail = db.get_invoice_audit_trail(invoice_id)
            shipments = trail.get("shipments", [])
            shipment_date = shipments[0]["shipment_date"] if shipments else None

            sample_data = {
                "transaction_amount": amount,
                "invoice_amount": inv["amount"],
                "supplier_id": inv["supplier_id"],
                "buyer_id": inv["buyer_id"],
                "carrier": shipments[0]["carrier"] if shipments else "None",
                "invoice_date": inv["invoice_date"],
                "shipment_date": shipment_date,
                "payment_date": timestamp,
            }

            pred = predict_transaction_risk(sample_data)
            explanation_data = explain_transaction_risk(sample_data)

            db.record_risk_score(
                invoice_id=invoice_id,
                transaction_id=transaction_id,
                fraud_probability=pred["fraud_probability"],
                risk_level=pred["risk_level"],
                model_version=pred.get("model_version", "v1.2.0-xgb"),
                explanation=explanation_data.get("summary_text", "Automated risk analysis completed."),
                top_features=str(explanation_data.get("top_factors", {})),
                shap_summary=explanation_data.get("summary_text", ""),
                default_probability=pred.get("default_probability", 0.0)
            )
            logger.info(f"AI Risk evaluated for {invoice_id}: {pred['risk_level']} (Prob: {pred['fraud_probability']:.2%})")
        except Exception as ex:
            logger.warning(f"Could not auto-trigger AI risk scoring: {ex}")

    def poll_events(self):
        """Polls latest blocks for smart contract events."""
        if not self.is_connected or not self.contract:
            logger.debug("Cannot poll events: live node disconnected.")
            return

        try:
            current_block = self.w3.eth.block_number
            if current_block <= self.last_checked_block:
                return

            from_block = self.last_checked_block + 1
            to_block = min(current_block, from_block + 500)

            # Query InvoiceCreated events
            inv_filter = self.contract.events.InvoiceCreated.create_filter(from_block=from_block, to_block=to_block)
            for evt in inv_filter.get_all_entries():
                self.process_invoice_created_event(evt["args"], evt["transactionHash"].hex(), evt["blockNumber"])

            # Query ShipmentConfirmed events
            ship_filter = self.contract.events.ShipmentConfirmed.create_filter(from_block=from_block, to_block=to_block)
            for evt in ship_filter.get_all_entries():
                self.process_shipment_confirmed_event(evt["args"], evt["transactionHash"].hex(), evt["blockNumber"])

            # Query PaymentReleased events
            pay_filter = self.contract.events.PaymentReleased.create_filter(from_block=from_block, to_block=to_block)
            for evt in pay_filter.get_all_entries():
                self.process_payment_released_event(evt["args"], evt["transactionHash"].hex(), evt["blockNumber"])

            self.last_checked_block = to_block
        except Exception as ex:
            logger.error(f"Error while polling blockchain events: {ex}")
            # Reconnect attempt
            self.connect()


listener = BlockchainEventListener()

if __name__ == "__main__":
    logger.info("Starting TrustChain SCM Event Listener (Press Ctrl+C to stop)...")
    try:
        while True:
            listener.poll_events()
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Listener stopped.")
