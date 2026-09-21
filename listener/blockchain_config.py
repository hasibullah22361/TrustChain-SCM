"""
TrustChain SCM - Blockchain Configuration & Web3 Provider
Handles Web3 provider connection, Sepolia/Local RPC endpoints,
and embedded ABI specifications for the event listener and caller.
"""

import os
import json
import logging
from typing import Optional, Tuple
from web3 import Web3
from web3.contract import Contract
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("trustchain.web3")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Environment parameters
RPC_URL = os.getenv("RPC_URL", "https://rpc.sepolia.org")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x5FbDB2315678afecb367f032d93F642f64180aa3")
CHAIN_ID = int(os.getenv("CHAIN_ID", "11155111"))
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

# Complete Contract ABI for SupplyChainFinance / TrustChain
TRUSTCHAIN_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "invoiceId", "type": "string"},
            {"indexed": True, "name": "supplier", "type": "address"},
            {"indexed": True, "name": "buyer", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "dueDate", "type": "uint256"},
            {"indexed": False, "name": "itemDescription", "type": "string"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "InvoiceCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "invoiceId", "type": "string"},
            {"indexed": False, "name": "carrier", "type": "string"},
            {"indexed": False, "name": "trackingNumber", "type": "string"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "ShipmentConfirmed",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "invoiceId", "type": "string"},
            {"indexed": True, "name": "supplier", "type": "address"},
            {"indexed": False, "name": "requestedAmount", "type": "uint256"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "FinancingRequested",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "invoiceId", "type": "string"},
            {"indexed": True, "name": "lender", "type": "address"},
            {"indexed": False, "name": "fundedAmount", "type": "uint256"},
            {"indexed": False, "name": "interestRateBps", "type": "uint256"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "FinancingApproved",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "invoiceId", "type": "string"},
            {"indexed": True, "name": "buyer", "type": "address"},
            {"indexed": False, "name": "amountPaid", "type": "uint256"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "PaymentReleased",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "invoiceId", "type": "string"},
            {"indexed": False, "name": "riskScore", "type": "uint256"},
            {"indexed": False, "name": "isFlagged", "type": "bool"},
            {"indexed": False, "name": "reason", "type": "string"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "RiskScoreUpdated",
        "type": "event"
    },
    {
        "inputs": [
            {"name": "_invoiceId", "type": "string"},
            {"name": "_buyer", "type": "address"},
            {"name": "_amount", "type": "uint256"},
            {"name": "_dueDate", "type": "uint256"},
            {"name": "_itemDescription", "type": "string"}
        ],
        "name": "createInvoice",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "_invoiceId", "type": "string"},
            {"name": "_carrier", "type": "string"},
            {"name": "_trackingNumber", "type": "string"}
        ],
        "name": "confirmShipment",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "_invoiceId", "type": "string"}
        ],
        "name": "releasePayment",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "_invoiceId", "type": "string"}
        ],
        "name": "getInvoice",
        "outputs": [
            {"name": "invoiceId", "type": "string"},
            {"name": "supplier", "type": "address"},
            {"name": "buyer", "type": "address"},
            {"name": "lender", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "dueDate", "type": "uint256"},
            {"name": "status", "type": "uint8"},
            {"name": "riskScore", "type": "uint256"},
            {"name": "isFlagged", "type": "bool"},
            {"name": "carrier", "type": "string"},
            {"name": "trackingNumber", "type": "string"},
            {"name": "createdAt", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getInvoiceCount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def get_web3_connection(rpc_url: Optional[str] = None) -> Tuple[Optional[Web3], bool]:
    """
    Attempts to establish a Web3 connection.
    Returns (w3_instance, is_live_connected).
    """
    endpoint = rpc_url or RPC_URL
    try:
        w3 = Web3(Web3.HTTPProvider(endpoint, request_kwargs={"timeout": 5}))
        if w3.is_connected():
            logger.info(f"Web3 connected to blockchain RPC at: {endpoint} (Chain ID: {w3.eth.chain_id})")
            return w3, True
        else:
            logger.warning(f"Web3 endpoint {endpoint} is not responding. Operating in Demo / Simulator mode.")
            return None, False
    except Exception as ex:
        logger.warning(f"Web3 connection error: {ex}. Operating in Demo / Simulator mode.")
        return None, False


def get_contract_instance(w3: Optional[Web3] = None, contract_addr: Optional[str] = None) -> Optional[Contract]:
    """Returns a web3.eth.contract instance if Web3 is active and contract address is valid."""
    if not w3 or not w3.is_connected():
        return None
    addr = contract_addr or CONTRACT_ADDRESS
    try:
        checksum_addr = Web3.to_checksum_address(addr)
        contract = w3.eth.contract(address=checksum_addr, abi=TRUSTCHAIN_ABI)
        return contract
    except Exception as ex:
        logger.error(f"Failed to instantiate contract at {addr}: {ex}")
        return None
