-- ==========================================================
-- TrustChain SCM - PostgreSQL Relational Database Schema
-- Multi-Tier Supply Chain Finance & Fraud Detection Platform
-- ==========================================================

-- 1. Parties Table: Counterparties (Suppliers, Buyers, Lenders)
CREATE TABLE IF NOT EXISTS parties (
    id SERIAL PRIMARY KEY,
    party_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    party_type VARCHAR(32) NOT NULL CHECK (party_type IN ('SUPPLIER', 'BUYER', 'LENDER')),
    wallet_address VARCHAR(42) NOT NULL,
    risk_rating VARCHAR(16) DEFAULT 'STANDARD',
    country VARCHAR(64) DEFAULT 'USA',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_parties_party_id ON parties(party_id);
CREATE INDEX IF NOT EXISTS idx_parties_wallet ON parties(wallet_address);

-- 2. Invoices Table: Trade Receivables Ledger
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    invoice_id VARCHAR(64) UNIQUE NOT NULL,
    supplier_id VARCHAR(64) NOT NULL REFERENCES parties(party_id) ON DELETE CASCADE,
    buyer_id VARCHAR(64) NOT NULL REFERENCES parties(party_id) ON DELETE CASCADE,
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(8) DEFAULT 'USD',
    item_description TEXT,
    invoice_date TIMESTAMP WITH TIME ZONE NOT NULL,
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(32) DEFAULT 'CREATED' CHECK (status IN (
        'CREATED',
        'SHIPMENT_CONFIRMED',
        'FINANCING_REQUESTED',
        'FINANCED',
        'PAID',
        'FLAGGED_FRAUD'
    )),
    blockchain_tx_hash VARCHAR(66),
    block_number BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_invoices_invoice_id ON invoices(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_id);
CREATE INDEX IF NOT EXISTS idx_invoices_buyer ON invoices(buyer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_tx_hash ON invoices(blockchain_tx_hash);

-- 3. Shipments Table: Logistics and Carrier Tracking
CREATE TABLE IF NOT EXISTS shipments (
    id SERIAL PRIMARY KEY,
    shipment_id VARCHAR(64) UNIQUE NOT NULL,
    invoice_id VARCHAR(64) NOT NULL REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    carrier VARCHAR(128) NOT NULL,
    tracking_number VARCHAR(128) NOT NULL,
    shipment_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(32) DEFAULT 'DISPATCHED' CHECK (status IN (
        'DISPATCHED',
        'IN_TRANSIT',
        'DELIVERED',
        'DELAYED'
    )),
    blockchain_tx_hash VARCHAR(66),
    block_number BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shipments_shipment_id ON shipments(shipment_id);
CREATE INDEX IF NOT EXISTS idx_shipments_invoice_id ON shipments(invoice_id);

-- 4. Transactions Table: On-Chain Supply Chain Events
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(64) UNIQUE NOT NULL,
    invoice_id VARCHAR(64) NOT NULL REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    transaction_type VARCHAR(64) NOT NULL CHECK (transaction_type IN (
        'INVOICE_CREATED',
        'SHIPMENT_CONFIRMED',
        'FINANCING_REQUESTED',
        'FINANCING_APPROVED',
        'PAYMENT_RELEASED',
        'RISK_SCORE_UPDATED'
    )),
    amount NUMERIC(14, 2) DEFAULT 0.00,
    sender_address VARCHAR(42),
    receiver_address VARCHAR(42),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    blockchain_tx_hash VARCHAR(66) UNIQUE NOT NULL,
    block_number BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_tx_id ON transactions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_transactions_invoice ON transactions(invoice_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_transactions_tx_hash ON transactions(blockchain_tx_hash);

-- 5. Risk Scores Table: AI/ML Inference & Explainability Audit Log
CREATE TABLE IF NOT EXISTS risk_scores (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(64) REFERENCES transactions(transaction_id) ON DELETE SET NULL,
    invoice_id VARCHAR(64) NOT NULL REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    fraud_probability REAL NOT NULL CHECK (fraud_probability >= 0.0 AND fraud_probability <= 1.0),
    default_probability REAL DEFAULT 0.0 CHECK (default_probability >= 0.0 AND default_probability <= 1.0),
    risk_level VARCHAR(16) NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    model_version VARCHAR(64) NOT NULL,
    explanation TEXT,
    top_features TEXT,
    shap_summary TEXT,
    is_flagged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_scores_invoice ON risk_scores(invoice_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_level ON risk_scores(risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_scores_prob ON risk_scores(fraud_probability);
