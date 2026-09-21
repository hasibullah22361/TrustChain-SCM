-- ==========================================================
-- TrustChain SCM - Seed Data
-- Realistic Supply Chain Parties, Invoices & Event Records
-- ==========================================================

-- Clean existing data if reseeding
DELETE FROM risk_scores;
DELETE FROM transactions;
DELETE FROM shipments;
DELETE FROM invoices;
DELETE FROM parties;

-- 1. Insert Core Ecosystem Parties
INSERT INTO parties (party_id, name, party_type, wallet_address, risk_rating, country) VALUES
('SUPP-GLOBAL-01', 'AeroTech Components Ltd', 'SUPPLIER', '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', 'AAA', 'Germany'),
('SUPP-NEXUS-02',  'Apex Precision Sensors',  'SUPPLIER', '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC', 'A', 'Japan'),
('SUPP-TITAN-03',  'Titan Raw Materials Corp','SUPPLIER', '0x90F79bf6EB2c4f870365E785982E1f101E93b906', 'BBB', 'South Korea'),
('SUPP-SUSP-04',   'ShadowShell Holdings Inc', 'SUPPLIER', '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', 'HIGH_RISK', 'Seychelles'),
('BUYER-OMEGA-01', 'Omega Automotive Group',  'BUYER',    '0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc', 'AAA', 'USA'),
('BUYER-VORTEX-02','Vortex Aerospace Inc',   'BUYER',    '0x976EA74026E726554dB657fA54763abd0C3a0aa9', 'AA', 'USA'),
('BUYER-QUICK-03', 'FlashRetail Logistics',   'BUYER',    '0x14dC79964da2C08b23698B3D3cc7Ca32193d9955', 'HIGH_RISK', 'Panama'),
('LEND-ALPHA-01',  'LiquidityBridge Capital', 'LENDER',   '0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f', 'AAA', 'UK'),
('LEND-BETA-02',   'TradeFlow Global Credit', 'LENDER',   '0xa0Ee7A142d267C1f36714E4a8F75612F20a79720', 'AAA', 'Switzerland');

-- 2. Insert Realistic Invoices (Normal & Injected Anomalies)
INSERT INTO invoices (invoice_id, supplier_id, buyer_id, amount, currency, item_description, invoice_date, due_date, status, blockchain_tx_hash, block_number) VALUES
-- Normal standard automotive supply flow
('INV-2026-001', 'SUPP-GLOBAL-01', 'BUYER-OMEGA-01', 125000.00, 'USD', '500x Titanium Turbine Blades Grade 5', '2026-09-01 08:30:00+00', '2026-10-31 00:00:00+00', 'PAID', '0x3a4b7f8c9d0e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b', 18450100),
-- Normal precision electronics flow
('INV-2026-002', 'SUPP-NEXUS-02', 'BUYER-VORTEX-02', 88500.00, 'USD', '1200x MEMS Gyroscope Precision Sensors', '2026-09-03 10:15:00+00', '2026-11-03 00:00:00+00', 'FINANCED', '0x1f2e3d4c5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e', 18450250),
-- Legitimate standard metals supply
('INV-2026-003', 'SUPP-TITAN-03', 'BUYER-OMEGA-01', 310000.00, 'USD', '40 Metric Tons Lightweight Structural Aluminum', '2026-09-05 14:00:00+00', '2026-12-05 00:00:00+00', 'SHIPMENT_CONFIRMED', '0x8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b', 18450420),
-- INJECTED FRAUD 1: Phantom shipment & rapid settlement (Ghost Carrier)
('INV-2026-004', 'SUPP-SUSP-04', 'BUYER-QUICK-03', 450000.00, 'USD', 'High-Frequency Semiconductor Wafers (Unverified)', '2026-09-08 02:11:00+00', '2026-09-10 00:00:00+00', 'FLAGGED_FRAUD', '0x99a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8', 18450600),
-- Normal manufacturing run
('INV-2026-005', 'SUPP-GLOBAL-01', 'BUYER-VORTEX-02', 64200.00, 'USD', 'High-temp Ceramic Exhaust Couplings', '2026-09-10 11:20:00+00', '2026-11-10 00:00:00+00', 'PAID', '0x4f5e6d7c8b9a0f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e', 18450780),
-- INJECTED FRAUD 2: Amount deviation & duplicate invoice attempt
('INV-2026-006', 'SUPP-SUSP-04', 'BUYER-OMEGA-01', 500000.00, 'USD', 'Bulk Specialized Rare Earth Elements', '2026-09-12 23:45:00+00', '2026-09-25 00:00:00+00', 'FLAGGED_FRAUD', '0x7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d', 18450910),
-- Normal ongoing contract
('INV-2026-007', 'SUPP-NEXUS-02', 'BUYER-OMEGA-01', 42000.00, 'USD', 'Automated Optical Inspection Modules', '2026-09-14 09:00:00+00', '2026-11-14 00:00:00+00', 'CREATED', '0x5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a', 18451120),
-- INJECTED FRAUD 3: Abnormal round sum with rapid financing demand
('INV-2026-008', 'SUPP-SUSP-04', 'BUYER-QUICK-03', 250000.00, 'USD', 'Consulting & Intellectual Property Licensing', '2026-09-15 03:14:00+00', '2026-09-20 00:00:00+00', 'FLAGGED_FRAUD', '0x6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d', 18451300),
-- Normal logistics flow
('INV-2026-009', 'SUPP-TITAN-03', 'BUYER-VORTEX-02', 175000.00, 'USD', 'Reinforced Carbon Composite Panels', '2026-09-17 13:40:00+00', '2026-11-30 00:00:00+00', 'PAID', '0x2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b', 18451480),
-- Normal raw material run
('INV-2026-010', 'SUPP-GLOBAL-01', 'BUYER-OMEGA-01', 94000.00, 'USD', 'Cryogenic Valves and Actuators Batch #4', '2026-09-19 16:15:00+00', '2026-11-19 00:00:00+00', 'CREATED', '0x1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e', 18451650);

-- 3. Insert Shipments
INSERT INTO shipments (shipment_id, invoice_id, carrier, tracking_number, shipment_date, status, blockchain_tx_hash, block_number) VALUES
('SHIP-2026-001', 'INV-2026-001', 'DHL Global Express', 'DHL-7739182390', '2026-09-03 14:00:00+00', 'DELIVERED', '0xaa11bb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66', 18450150),
('SHIP-2026-002', 'INV-2026-002', 'FedEx International', 'FDX-9928192019', '2026-09-05 10:30:00+00', 'IN_TRANSIT', '0xbb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77', 18450280),
('SHIP-2026-003', 'INV-2026-003', 'Maersk Ocean Freight','MSK-4481029481', '2026-09-08 08:00:00+00', 'DISPATCHED', '0xcc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88', 18450460),
('SHIP-2026-005', 'INV-2026-005', 'Kuehne+Nagel Logistics','KNN-3391028471', '2026-09-12 11:00:00+00', 'DELIVERED', '0xdd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99', 18450810),
('SHIP-2026-009', 'INV-2026-009', 'DB Schenker Global',   'DBS-1102938472', '2026-09-18 15:20:00+00', 'DELIVERED', '0xee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99bb00', 18451510);

-- 4. Insert On-Chain Transactions
INSERT INTO transactions (transaction_id, invoice_id, transaction_type, amount, sender_address, receiver_address, timestamp, blockchain_tx_hash, block_number) VALUES
-- Normal flow for INV-001
('TXN-2026-001A', 'INV-2026-001', 'INVOICE_CREATED', 125000.00, '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', '0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc', '2026-09-01 08:30:00+00', '0x3a4b7f8c9d0e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b', 18450100),
('TXN-2026-001B', 'INV-2026-001', 'SHIPMENT_CONFIRMED', 0.00, '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', '0x0000000000000000000000000000000000000000', '2026-09-03 14:00:00+00', '0xaa11bb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66', 18450150),
('TXN-2026-001C', 'INV-2026-001', 'PAYMENT_RELEASED', 125000.00, '0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc', '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', '2026-09-15 16:30:00+00', '0x55aa66bb77cc88dd99ee00ff11aa22bb33cc44dd55ee66ff77aa88bb99cc00dd', 18450190),

-- Flow for INV-004 (Fraudulent / Suspicious Payment)
('TXN-2026-004A', 'INV-2026-004', 'INVOICE_CREATED', 450000.00, '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', '0x14dC79964da2C08b23698B3D3cc7Ca32193d9955', '2026-09-08 02:11:00+00', '0x99a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8', 18450600),
('TXN-2026-004B', 'INV-2026-004', 'PAYMENT_RELEASED', 450000.00, '0x14dC79964da2C08b23698B3D3cc7Ca32193d9955', '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', '2026-09-08 04:15:00+00', '0x8899aabbccddeeff00112233445566778899aabbccddeeff0011223344556677', 18450610),

-- Flow for INV-005 (Normal)
('TXN-2026-005A', 'INV-2026-005', 'INVOICE_CREATED', 64200.00, '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', '0x976EA74026E726554dB657fA54763abd0C3a0aa9', '2026-09-10 11:20:00+00', '0x4f5e6d7c8b9a0f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e', 18450780),
('TXN-2026-005B', 'INV-2026-005', 'SHIPMENT_CONFIRMED', 0.00, '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', '0x0000000000000000000000000000000000000000', '2026-09-12 11:00:00+00', '0xdd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99', 18450810),
('TXN-2026-005C', 'INV-2026-005', 'PAYMENT_RELEASED', 64200.00, '0x976EA74026E726554dB657fA54763abd0C3a0aa9', '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', '2026-09-20 14:10:00+00', '0x77889900aabbccddeeff00112233445566778899aabbccddeeff001122334455', 18450890),

-- Flow for INV-006 (Fraudulent Attempt)
('TXN-2026-006A', 'INV-2026-006', 'INVOICE_CREATED', 500000.00, '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', '0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc', '2026-09-12 23:45:00+00', '0x7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d', 18450910),

-- Flow for INV-008 (Suspicious Financing Request)
('TXN-2026-008A', 'INV-2026-008', 'INVOICE_CREATED', 250000.00, '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', '0x14dC79964da2C08b23698B3D3cc7Ca32193d9955', '2026-09-15 03:14:00+00', '0x6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d', 18451300),
('TXN-2026-008B', 'INV-2026-008', 'FINANCING_REQUESTED', 250000.00, '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', '0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f', '2026-09-15 03:18:00+00', '0x11223344556677889900aabbccddeeff00112233445566778899aabbccddeeff', 18451310);

-- 5. Insert AI/ML Risk Scores & SHAP Explanations
INSERT INTO risk_scores (transaction_id, invoice_id, fraud_probability, default_probability, risk_level, model_version, explanation, top_features, shap_summary, is_flagged) VALUES
('TXN-2026-001C', 'INV-2026-001', 0.042, 0.015, 'LOW', 'v1.2.0-xgb', 
 'Transaction displays verified physical delivery by Tier-1 carrier, typical settlement cadence (12 days), and counterparties with 100% verified fulfillment history.',
 '{"carrier_verification": -0.42, "settlement_delay_norm": -0.38, "counterparty_rating": -0.35}',
 'Normal commercial flow. Negligible fraud risk.', FALSE),

('TXN-2026-004B', 'INV-2026-004', 0.946, 0.820, 'HIGH', 'v1.2.0-xgb',
 'CRITICAL ANOMALY: Settlement released only 2.06 hours after invoice creation with no physical shipment confirmation. Counterparty previously flagged in suspicious entities registry.',
 '{"ghost_shipment_flag": +0.88, "payment_speed_anomaly": +0.76, "supplier_risk_tier": +0.64, "round_amount_score": +0.32}',
 'Ghost shipment anomaly. Rapid round-sum liquidation detected.', TRUE),

('TXN-2026-005C', 'INV-2026-005', 0.068, 0.021, 'LOW', 'v1.2.0-xgb',
 'Standard aerospace parts batch fulfillment with verified carrier tracking, standard Net-30 payment schedule, and consistent amount history.',
 '{"carrier_verification": -0.36, "time_delta_realistic": -0.31, "amount_variance_low": -0.28}',
 'Normal commercial flow. Verified logistics chain.', FALSE),

('TXN-2026-006A', 'INV-2026-006', 0.882, 0.740, 'HIGH', 'v1.2.0-xgb',
 'HIGH RISK: Unusually large round-sum invoice ($500,000) issued during non-business hours (23:45 UTC) from an entity with elevated fraud history.',
 '{"amount_deviation_extreme": +0.81, "off_hours_timestamp": +0.52, "supplier_prior_flags": +0.69}',
 'Potential duplicate or phantom receivable submission.', TRUE),

('TXN-2026-008B', 'INV-2026-008', 0.894, 0.790, 'HIGH', 'v1.2.0-xgb',
 'HIGH RISK: Immediate 100% receivables financing request submitted 4 minutes after invoice creation with no Bill of Lading attached. Shell entity behavior.',
 '{"financing_timing_immediate": +0.85, "missing_bol": +0.72, "supplier_fraud_rating": +0.61}',
 'Early financing fraud vector identified.', TRUE);
