# TrustChain SCM: AI-Powered Supply Chain Finance & Fraud Detection

[![Solidity](https://img.shields.io/badge/Solidity-0.8.20-blue.svg)](https://soliditylang.org/)
[![Hardhat](https://img.shields.io/badge/Hardhat-2.20+-yellow.svg)](https://hardhat.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](https://python.org/)
[![XGBoost](https://img.shields.io/badge/XGBoost-Class_Balanced-orange.svg)](https://xgboost.readthedocs.io/)
[![SHAP](https://img.shields.io/badge/SHAP-TreeExplainer-purple.svg)](https://shap.readthedocs.io/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red.svg)](https://streamlit.io/)
[![Database](https://img.shields.io/badge/PostgreSQL-Dual_Engine_SQLite-336791.svg)](https://www.postgresql.org/)

TrustChain SCM is a portfolio-grade, production-structured trade receivables finance platform that integrates:
**Supplier / Buyer / Lender → Blockchain Ledger → SQL Database → XGBoost / SHAP AI Risk Engine → Interactive Streamlit Dashboard**.

---

## 1. System Architecture

```text
                                  +---------------------------------------+
                                  |     Ecosystem Counterparties          |
                                  |  (Supplier / Buyer / Lender / Bank)   |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |     Smart Contract Layer              |
                                  |  (SupplyChainFinance.sol / Hardhat)   |
                                  |  - InvoiceCreated                     |
                                  |  - ShipmentConfirmed                  |
                                  |  - PaymentReleased                    |
                                  +-------------------+-------------------+
                                                      |
                                       web3.py Event  | Listener
                                                      v
                                  +---------------------------------------+
                                  |       Relational SQL Layer            |
                                  |  (PostgreSQL / Resilient SQLite)      |
                                  |  - parties, invoices, shipments       |
                                  |  - transactions, risk_scores          |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |       AI / ML Risk Scoring Engine     |
                                  |  (XGBoost Classifier + SHAP TreeExp)  |
                                  |  - Feature engineering pipeline       |
                                  |  - Class-balanced fraud scoring       |
                                  |  - Local factor attribution           |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |      Streamlit Auditor Dashboard      |
                                  |  - Executive KPI cards                |
                                  |  - Filterable transactions ledger     |
                                  |  - Flagged fraud review queue         |
                                  |  - Visual invoice provenance trail    |
                                  |  - Live AI scenario simulation lab    |
                                  |  - Cryptographic blockchain explorer  |
                                  +---------------------------------------+
```

---

## 2. Directory Structure

```text
trustchain-scm/
├── contracts/
│   ├── SupplyChainFinance.sol       # Primary Solidity contract
│   ├── TrustChain.sol               # Remix IDE compatible alias
│   ├── hardhat.config.js            # Hardhat network & compiler configuration
│   ├── package.json                 # Contracts dependencies & scripts
│   ├── scripts/
│   │   └── deploy.js                # Deployment script to Sepolia or Local
│   └── test/
│       └── SupplyChainFinance.test.js # Comprehensive contract unit tests
│
├── listener/
│   ├── blockchain_config.py         # Web3 provider & embedded contract ABI
│   ├── event_listener.py            # Real-time event listener & auto-AI scoring
│   └── simulator.py                 # Deterministic blockchain event simulator
│
├── database/
│   ├── schema.sql                   # PostgreSQL standard DDL relational schema
│   ├── seed.sql                     # Realistic trade scenarios & seed queries
│   └── database.py                  # Dual-engine SQLAlchemy database manager
│
├── model/
│   ├── generate_data.py             # Realistic synthetic data generator (8.5% fraud)
│   ├── feature_engineering.py       # Scikit-learn ColumnTransformer pipeline
│   ├── train_model.py               # XGBoost + baseline RandomForest training
│   ├── predict.py                   # Production inference & threshold service
│   ├── explain.py                   # SHAP TreeExplainer local attribution
│   └── models/                      # Serialized preprocessor & model weights
│
├── dashboard/
│   └── app.py                       # Multi-page interactive Streamlit dashboard
│
├── data/
│   ├── raw/                         # Raw synthetic transactions CSV
│   └── processed/
│
├── tests/
│   ├── test_database.py             # Database CRUD & deduplication tests
│   ├── test_ml_pipeline.py          # ML feature pipeline & SHAP tests
│   └── test_end_to_end.py           # Complete 18-step integration workflow
│
├── notebooks/
│   └── trustchain_exploration.ipynb # Jupyter EDA & model visualization
│
├── .env.example                     # Environment template
├── .env                             # Local active configuration
├── requirements.txt                 # Python dependencies
├── package.json                     # Root npm configuration
├── hardhat.config.js                # Root Hardhat configuration
└── README.md                        # Documentation
```

---

## 3. Technology Stack

- **Blockchain**: Solidity `^0.8.20`, Hardhat, ethers.js, web3.py, Sepolia Testnet, MetaMask & Remix compatible.
- **Backend & Data**: Python 3.11+, SQLAlchemy 2.0+, PostgreSQL (with automatic zero-friction SQLite fallback for instant execution), psycopg3.
- **Machine Learning**: pandas, NumPy, scikit-learn, XGBoost (`scale_pos_weight` tuned for class imbalance), SHAP (`TreeExplainer`).
- **Dashboard**: Streamlit, Plotly Express & Graph Objects, responsive custom CSS cards with dark theme.

---

## 4. Quick Start Installation

### Step 1: Virtual Environment Setup
```bash
# Clone the repository
git clone https://github.com/your-org/trustchain-scm.git
cd trustchain-scm

# Using standard Python or uv
uv venv
.venv\Scripts\activate      # Windows
# or source .venv/bin/activate  # Linux/macOS

# Install dependencies
uv pip install -r requirements.txt
```

### Step 2: Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default parameters in `.env`:
```env
DATABASE_URL=sqlite:///database/trustchain.db
RPC_URL=https://rpc.sepolia.org
CHAIN_ID=11155111
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
DEMO_MODE=true
RISK_THRESHOLD_LOW=0.30
RISK_THRESHOLD_HIGH=0.70
```
*Note: To connect to PostgreSQL, set `DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/trustchain_db`.*

---

## 5. Running the Complete System

### 1. Initialize Database & Seed Data
```bash
python database/database.py
```

### 2. Generate Synthetic Dataset & Train AI Models
```bash
# Generate 6,000 realistic supply chain records with 8.5% fraud minority class
python model/generate_data.py

# Fit feature pipeline and train class-balanced XGBoost classifier
python model/train_model.py

# Verify SHAP explainability attributions
python model/explain.py
```

### 3. Launch Streamlit Analytics Dashboard
```bash
streamlit run dashboard/app.py
```
Open **http://localhost:8501** in your browser.

---

## 6. Smart Contracts & Hardhat

### Compile Contracts
```bash
cd contracts
npm install
npx hardhat compile
```

### Run Smart Contract Tests
```bash
npx hardhat test
```
Tests verify:
- Invoice creation with non-zero amounts and future due dates
- Duplicate invoice rejection
- Shipment confirmation from authorized counterparties
- Receivables financing requests and lender approvals
- Settlement payment release
- AI risk score updates and on-chain fraud flagging

### Deploy Contract to Local Hardhat or Sepolia
```bash
# Local deployment
npx hardhat run scripts/deploy.js --network localhost

# Sepolia testnet deployment (requires RPC_URL and PRIVATE_KEY in .env)
npx hardhat run scripts/deploy.js --network sepolia
```

---

## 7. Running Automated Test Suites

```bash
# Run all unit and end-to-end integration tests
python -m unittest discover -s tests -p "test_*.py"
```

The test suite validates:
1. `test_database.py`: Relational schemas, party upserts, invoice records, and blockchain transaction hash deduplication.
2. `test_ml_pipeline.py`: Feature engineering pipeline, XGBoost probability calibration, and SHAP TreeExplainer attributions.
3. `test_end_to_end.py`: The complete 18-step lifecycle from simulated block creation to SQL ingestion, automated risk scoring, and auditor audit trail rendering.

---

## 8. Live Demonstration Walkthrough

1. **Dashboard Overview**: Review real-time KPIs (Total Invoices, Total Volume, Paid Volume, Flagged Fraud, Fraud Rate) and Plotly receivable charts.
2. **Transactions Ledger**: Filter transactions by risk tier (`HIGH`, `MEDIUM`, `LOW`) or search by invoice ID or hash.
3. **Flagged Transactions (Risk Center)**: Inspect suspicious transactions (e.g. `INV-2026-004`). View the SHAP waterfall/bar chart showing exact drivers:
   - `+ Short payment interval: only 2.06 hours (expected > 720 hours)`
   - `+ Missing carrier verification (Ghost shipment)`
   - `+ Counterparty prior fraud record`
4. **Invoice Audit Trail**: Select any invoice to see the 4-stage visual timeline:
   `Invoice Created -> Shipment Confirmed -> Payment Released -> AI Risk Analysis`.
5. **AI Risk Analysis Lab**: Test clean vs fraud scenarios interactively in real time. Adjust sliders for payment interval, amount deviation, and prior fraud count, then execute instant XGBoost + SHAP inference.
6. **Blockchain Explorer**: View sequential block numbers, transaction hashes, and event logs. Use the built-in demo simulator tool to emit a new on-chain transaction live!

---

## 9. License & Disclaimers

- **License**: MIT License.
- **Disclaimer**: This platform generates probabilistic fraud risk assessments intended to augment human auditor workflows. Risk scores reflect statistical anomaly metrics and do not constitute definitive legal assertions of fraudulent activity.
#   T r u s t C h a i n - S C M  
 