"""
TrustChain SCM - Interactive Streamlit Analytics Dashboard
AI-Powered Supply Chain Finance & Fraud Detection Platform
Connecting Blockchain Events -> SQL Database -> XGBoost / SHAP AI Models -> Unified Auditor UI
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Configure page layout and visual theme
st.set_page_config(
    page_title="TrustChain SCM | AI Supply Chain Finance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.database import db
from model.predict import predict_transaction_risk, RISK_THRESHOLD_LOW, RISK_THRESHOLD_HIGH
from model.explain import explain_transaction_risk
from listener.simulator import simulator
from listener.blockchain_config import RPC_URL, CONTRACT_ADDRESS, DEMO_MODE

# Ensure database is initialized on startup if deployed to a fresh container
try:
    db.init_db(seed=True)
except Exception:
    pass

# Custom CSS for modern glassmorphism, responsive cards, and clean typography
st.markdown("""
<style>
    /* Global Styling */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
    }
    
    /* Top Banner */
    .top-banner {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.3);
    }
    .top-banner h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
        color: #F8FAFC;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .top-banner p {
        margin: 6px 0 0 0;
        color: #94A3B8;
        font-size: 0.95rem;
    }
    
    /* Metric Cards */
    .metric-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #3B82F6;
        transform: translateY(-2px);
    }
    .metric-label {
        font-size: 0.82rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 700;
        color: #F8FAFC;
        line-height: 1.2;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #64748B;
        margin-top: 4px;
    }
    
    /* Risk Badges */
    .badge-high {
        background-color: rgba(239, 68, 68, 0.18);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .badge-low {
        background-color: rgba(16, 185, 129, 0.18);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .badge-medium {
        background-color: rgba(245, 158, 11, 0.18);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
    }

    /* Audit Step Card */
    .timeline-step {
        background: #1E293B;
        border-left: 4px solid #3B82F6;
        border-radius: 0 8px 8px 0;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .timeline-step.flagged {
        border-left-color: #EF4444;
    }
    .timeline-step.verified {
        border-left-color: #10B981;
    }
    .hash-text {
        font-family: 'Courier New', monospace;
        font-size: 0.8rem;
        color: #60A5FA;
        word-break: break-all;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- Sidebar Navigation & System Telemetry ----------------

st.sidebar.image("https://img.icons8.com/isometric/96/shield.png", width=64)
st.sidebar.markdown("### **TrustChain SCM**")
st.sidebar.caption("AI-Powered Supply Chain Finance & Fraud Detection")

# Navigation menu
menu_selection = st.sidebar.radio(
    "Navigation",
    [
        "📊 Executive Dashboard",
        "📑 Transactions Ledger",
        "🚨 Flagged Transactions",
        "🔍 Invoice Audit Trail",
        "🤖 AI Risk Analysis Lab",
        "⛓️ Blockchain Explorer"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("System Telemetry")

# Environment indicator
app_mode = "Demo Mode (Simulated Ledger)" if DEMO_MODE else "Live Testnet (Sepolia)"
st.sidebar.info(f"**Mode:** {app_mode}")

db_status = "PostgreSQL (Active)" if db.is_postgres else "SQLite (Active Fallback)"
st.sidebar.markdown(f"**Database:** `{db_status}`")
st.sidebar.markdown(f"**Model:** `XGBoost v1.2.0 (Active)`")
st.sidebar.markdown(f"**Contract:** `{CONTRACT_ADDRESS[:6]}...{CONTRACT_ADDRESS[-4:]}`")

if st.sidebar.button("🔄 Reseed / Reset Demo Data"):
    db.init_db(seed=True)
    st.sidebar.success("Database re-initialized with realistic seed data.")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("TrustChain SCM © 2026 • Verified Audit Record")


# ---------------- Header Banner Component ----------------

def render_header(title: str, subtitle: str):
    st.markdown(f"""
    <div class="top-banner">
        <h1><span>🛡️</span> {title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# PAGE 1: EXECUTIVE DASHBOARD
# =========================================================================

if menu_selection == "📊 Executive Dashboard":
    render_header(
        "Executive Risk & Supply Chain Dashboard",
        "Real-time monitoring of commercial trade receivables, blockchain settlement logs, and AI anomaly detection."
    )

    metrics = db.get_dashboard_metrics()

    # Top KPI metric row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Invoices</div>
            <div class="metric-value">{metrics['total_invoices']}</div>
            <div class="metric-sub">Registered on-chain</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Transactions</div>
            <div class="metric-value">{metrics['total_transactions']}</div>
            <div class="metric-sub">Event log entries</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Volume</div>
            <div class="metric-value">${metrics['total_volume']:,.0f}</div>
            <div class="metric-sub">Trade receivables</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Paid Volume</div>
            <div class="metric-value">${metrics['total_paid_volume']:,.0f}</div>
            <div class="metric-sub">Settled payments</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Flagged Fraud</div>
            <div class="metric-value" style="color: #EF4444;">{metrics['flagged_transactions']}</div>
            <div class="metric-sub">Auditor review queue</div>
        </div>
        """, unsafe_allow_html=True)
    with c6:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Fraud Rate</div>
            <div class="metric-value" style="color: #F59E0B;">{metrics['fraud_rate']:.1f}%</div>
            <div class="metric-sub">Avg Risk: {metrics['average_risk_score']:.1%}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Visual Analytics Row
    invoices = db.get_all_invoices()
    df_inv = pd.DataFrame(invoices)

    col_chart1, col_chart2 = st.columns([3, 2])

    with col_chart1:
        st.subheader("Trade Receivable Volumes by Invoice")
        if not df_inv.empty:
            fig = px.bar(
                df_inv,
                x="invoice_id",
                y="amount",
                color="status",
                color_discrete_map={
                    "PAID": "#10B981",
                    "FINANCED": "#3B82F6",
                    "SHIPMENT_CONFIRMED": "#6366F1",
                    "CREATED": "#94A3B8",
                    "FLAGGED_FRAUD": "#EF4444"
                },
                labels={"amount": "Amount (USD)", "invoice_id": "Invoice ID", "status": "Status"},
                template="plotly_dark",
                height=350,
            )
            fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No invoice records to display.")

    with col_chart2:
        st.subheader("Invoice Status Distribution")
        if not df_inv.empty:
            status_counts = df_inv["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            fig_pie = px.pie(
                status_counts,
                values="count",
                names="status",
                hole=0.45,
                color="status",
                color_discrete_map={
                    "PAID": "#10B981",
                    "FINANCED": "#3B82F6",
                    "SHIPMENT_CONFIRMED": "#6366F1",
                    "CREATED": "#94A3B8",
                    "FLAGGED_FRAUD": "#EF4444"
                },
                template="plotly_dark",
                height=350
            )
            fig_pie.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No data available.")

    # Second Analytics Row: Risk distribution and Timeline
    col_t1, col_t2 = st.columns([2, 3])
    txns = db.get_transactions(limit=100)
    df_tx = pd.DataFrame(txns)

    with col_t1:
        st.subheader("Risk Score Distribution")
        if not df_tx.empty and "fraud_probability" in df_tx.columns:
            probs = df_tx["fraud_probability"].dropna()
            fig_hist = px.histogram(
                probs,
                nbins=12,
                labels={"value": "Fraud Probability Score"},
                template="plotly_dark",
                color_discrete_sequence=["#3B82F6"],
                height=300
            )
            fig_hist.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No transaction risk scores available.")

    with col_t2:
        st.subheader("Recent On-Chain Activity Feed")
        if not df_tx.empty:
            st.dataframe(
                df_tx[[
                    "transaction_id", "invoice_id", "transaction_type", "amount", "timestamp", "risk_level"
                ]].head(6),
                use_container_width=True,
                height=300
            )
        else:
            st.info("No recent transactions.")


# =========================================================================
# PAGE 2: TRANSACTIONS LEDGER
# =========================================================================

elif menu_selection == "📑 Transactions Ledger":
    render_header(
        "Structured Transaction & Event Ledger",
        "PostgreSQL analytics mirror of on-chain trade events with AI risk classifications."
    )

    txns = db.get_transactions(limit=150)
    df_tx = pd.DataFrame(txns)

    if not df_tx.empty:
        # Filter controls
        f1, f2, f3 = st.columns([2, 2, 3])
        with f1:
            risk_filter = st.selectbox("Filter by Risk Level", ["ALL", "LOW", "MEDIUM", "HIGH"])
        with f2:
            type_filter = st.selectbox(
                "Filter by Transaction Type",
                ["ALL", "INVOICE_CREATED", "SHIPMENT_CONFIRMED", "FINANCING_REQUESTED", "PAYMENT_RELEASED"]
            )
        with f3:
            search_query = st.text_input("Search (Invoice, Party, Tx Hash)", placeholder="e.g. INV-2026-004")

        filtered = df_tx.copy()
        if risk_filter != "ALL":
            filtered = filtered[filtered["risk_level"] == risk_filter]
        if type_filter != "ALL":
            filtered = filtered[filtered["transaction_type"] == type_filter]
        if search_query:
            q = search_query.lower()
            filtered = filtered[
                filtered["invoice_id"].str.lower().str.contains(q, na=False) |
                filtered["transaction_id"].str.lower().str.contains(q, na=False) |
                filtered["blockchain_tx_hash"].str.lower().str.contains(q, na=False)
            ]

        st.markdown(f"**Showing {len(filtered)} transactions:**")
        
        # Display formatted table
        display_cols = [
            "transaction_id", "invoice_id", "transaction_type", "amount",
            "fraud_probability", "risk_level", "timestamp", "blockchain_tx_hash"
        ]
        
        # Format styling for risk badges
        def style_risk(val):
            if val == "HIGH":
                return "color: #EF4444; font-weight: bold;"
            elif val == "MEDIUM":
                return "color: #F59E0B; font-weight: bold;"
            elif val == "LOW":
                return "color: #10B981; font-weight: bold;"
            return ""

        st.dataframe(
            filtered[display_cols].style.applymap(style_risk, subset=["risk_level"]),
            use_container_width=True,
            height=450
        )
    else:
        st.warning("No transactions recorded in database. Click 'Reseed Demo Data' in the sidebar.")


# =========================================================================
# PAGE 3: FLAGGED TRANSACTIONS (RISK CENTER)
# =========================================================================

elif menu_selection == "🚨 Flagged Transactions":
    render_header(
        "High-Risk Fraud & Default Review Queue",
        "Dedicated audit queue for transactions exceeding high-risk threshold (P(Fraud) > 70%). Powered by XGBoost and SHAP."
    )

    flagged = db.get_flagged_transactions()

    if not flagged:
        st.success("🎉 No high-risk transactions currently flagged in the system!")
    else:
        st.markdown(f"Found **{len(flagged)}** transactions requiring fraud analyst review:")

        # Transaction selection selector
        options = [f"{f['invoice_id']} | Score: {f['fraud_probability']:.1%} | {f['explanation'][:60]}..." for f in flagged]
        selected_idx = st.selectbox("Select Flagged Transaction for Deep Investigation:", range(len(flagged)), format_func=lambda i: options[i])

        item = flagged[selected_idx]

        st.markdown("---")

        c_left, c_right = st.columns([1, 1])

        with c_left:
            st.subheader("Transaction Summary")
            st.markdown(f"""
            - **Invoice ID:** `{item['invoice_id']}`
            - **Supplier:** `{item['supplier_id']}`
            - **Buyer:** `{item['buyer_id']}`
            - **Invoice Face Value:** `${item['invoice_amount']:,.2f}`
            - **Settlement Amount:** `${item.get('tx_amount') or item['invoice_amount']:,.2f}`
            - **Item Description:** {item.get('item_description', 'N/A')}
            - **Blockchain Tx Hash:**
            """)
            st.code(item.get("tx_hash") or item.get("inv_tx_hash", "0x0000000000000000000000000000000000000000"))

            st.markdown("#### Risk Assessment")
            st.markdown(f"""
            - **Fraud Probability:** <span class="badge-high">{item['fraud_probability']:.2%}</span>
            - **Credit Default Risk:** `{item.get('default_probability', 0.0):.2%}`
            - **Model Version:** `{item.get('model_version', 'v1.2.0-xgb')}`
            - **Decision:** <span class="badge-high">FLAGGED FOR MANUAL AUDIT</span>
            """, unsafe_allow_html=True)

        with c_right:
            st.subheader("SHAP Factor Attribution")
            st.markdown(f"**Auditor Narrative:**\n\n```text\n{item.get('explanation', 'High risk detected.')}\n```")

            # Parse top features for chart
            top_feat_raw = item.get("top_features")
            if top_feat_raw:
                try:
                    feat_dict = json.loads(top_feat_raw)
                    feat_names = list(feat_dict.keys())
                    feat_vals = list(feat_dict.values())
                    colors = ["#EF4444" if v > 0 else "#10B981" for v in feat_vals]

                    fig_shap = go.Figure(go.Bar(
                        x=feat_vals,
                        y=feat_names,
                        orientation="h",
                        marker_color=colors
                    ))
                    fig_shap.update_layout(
                        title="Local SHAP Feature Contributions (+ Fraud / - Trust)",
                        template="plotly_dark",
                        height=280,
                        margin=dict(l=10, r=10, t=35, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig_shap, use_container_width=True)
                except Exception as ex:
                    st.caption(f"Feature chart preview unavailable: {ex}")


# =========================================================================
# PAGE 4: INVOICE AUDIT TRAIL
# =========================================================================

elif menu_selection == "🔍 Invoice Audit Trail":
    render_header(
        "Complete Provenance & Lifecycle Audit Trail",
        "End-to-end cryptographic and physical verification connecting Blockchain -> SQL -> AI Risk Score."
    )

    invoices = db.get_all_invoices()
    if not invoices:
        st.warning("No invoices found.")
    else:
        inv_ids = [inv["invoice_id"] for inv in invoices]
        selected_inv_id = st.selectbox("Select Invoice to Inspect Lifecycle:", inv_ids)

        trail = db.get_invoice_audit_trail(selected_inv_id)
        inv = trail["invoice"]
        txns = trail["transactions"]
        shipments = trail["shipments"]
        risks = trail["risk_scores"]

        # Display Top Summary
        st.markdown(f"### Invoice: `{inv['invoice_id']}` — Amount: **${inv['amount']:,.2f} {inv['currency']}**")
        st.caption(f"Description: {inv.get('item_description', 'N/A')} | Supplier: {inv['supplier_id']} | Buyer: {inv['buyer_id']}")

        st.markdown("#### Chronological Audit Timeline")

        # Step 1: Invoice Created
        st.markdown(f"""
        <div class="timeline-step verified">
            <strong>Stage 1: Invoice Created & Anchored to Blockchain</strong><br>
            <span style="color: #94A3B8;">Registered on: {inv['invoice_date']} | Status: {inv['status']}</span><br>
            <span class="hash-text">Blockchain Hash: {inv.get('blockchain_tx_hash', 'N/A')}</span>
        </div>
        """, unsafe_allow_html=True)

        # Step 2: Shipment Confirmed
        if shipments:
            s = shipments[0]
            st.markdown(f"""
            <div class="timeline-step verified">
                <strong>Stage 2: Physical Logistics & Dispatch Confirmed</strong><br>
                <span style="color: #94A3B8;">Carrier: {s['carrier']} | Tracking: {s['tracking_number']} | Date: {s['shipment_date']}</span><br>
                <span class="hash-text">Logistics Hash: {s.get('blockchain_tx_hash', 'N/A')}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="timeline-step flagged">
                <strong>Stage 2: Physical Logistics (MISSING OR UNCONFIRMED)</strong><br>
                <span style="color: #EF4444;">No carrier tracking number registered. Potential phantom shipment anomaly.</span>
            </div>
            """, unsafe_allow_html=True)

        # Step 3: Payment Released
        pay_txn = next((t for t in txns if t["transaction_type"] == "PAYMENT_RELEASED"), None)
        if pay_txn:
            st.markdown(f"""
            <div class="timeline-step verified">
                <strong>Stage 3: Buyer Payment Settlement Released</strong><br>
                <span style="color: #94A3B8;">Amount Paid: ${pay_txn['amount']:,.2f} | Timestamp: {pay_txn['timestamp']}</span><br>
                <span class="hash-text">Settlement Hash: {pay_txn['blockchain_tx_hash']}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="timeline-step">
                <strong>Stage 3: Settlement Payment (Pending)</strong><br>
                <span style="color: #94A3B8;">Payment has not yet been executed on-chain.</span>
            </div>
            """, unsafe_allow_html=True)

        # Step 4: AI Model Risk Analysis
        if risks:
            r = risks[0]
            is_flagged = r.get("is_flagged", False)
            badge_class = "flagged" if is_flagged else "verified"
            st.markdown(f"""
            <div class="timeline-step {badge_class}">
                <strong>Stage 4: AI Model Risk Assessment & SHAP Validation</strong><br>
                <span style="color: #94A3B8;">Fraud Probability: <strong>{r['fraud_probability']:.2%}</strong> | Tier: <strong>{r['risk_level']}</strong> | Engine: {r['model_version']}</span><br>
                <p style="margin-top: 8px; font-size: 0.88rem; color: #E2E8F0;">{r.get('explanation', 'N/A')}</p>
            </div>
            """, unsafe_allow_html=True)


# =========================================================================
# PAGE 5: AI RISK ANALYSIS LAB (INTERACTIVE SIMULATOR)
# =========================================================================

elif menu_selection == "🤖 AI Risk Analysis Lab":
    render_header(
        "Interactive AI Risk Scoring & SHAP Explainability Lab",
        "Test custom trade receivables scenarios in real time. Compare clean commercial behavior vs injected fraud."
    )

    st.markdown("#### Scenario Configuration")

    col_ctrl1, col_ctrl2 = st.columns(2)

    with col_ctrl1:
        scenario_preset = st.selectbox(
            "Load Scenario Preset:",
            [
                "Custom Parameters",
                "Clean Normal Trade (Titanium Blades, Net-30, DHL)",
                "Anomaly 1: Phantom Ghost Shipment (Rapid 2-hr Settlement)",
                "Anomaly 2: High Amount Deviation (+150% Over Invoice)",
                "Anomaly 3: Shell Entity Round Amount ($500,000 at 02:00 AM)"
            ]
        )

    # Defaults
    def_inv_amt = 100000.0
    def_txn_amt = 100000.0
    def_carrier = "DHL Global Express"
    def_hours_to_pay = 720.0  # 30 days
    def_hist_fraud = 0
    def_is_night = False

    if "Clean Normal" in scenario_preset:
        def_inv_amt, def_txn_amt = 125000.0, 125000.0
        def_carrier = "DHL Global Express"
        def_hours_to_pay = 360.0
        def_hist_fraud = 0
    elif "Ghost Shipment" in scenario_preset:
        def_inv_amt, def_txn_amt = 450000.0, 450000.0
        def_carrier = "None"
        def_hours_to_pay = 2.0  # 2 hours!
        def_hist_fraud = 6
    elif "Amount Deviation" in scenario_preset:
        def_inv_amt, def_txn_amt = 100000.0, 240000.0
        def_carrier = "FedEx International"
        def_hours_to_pay = 240.0
        def_hist_fraud = 1
    elif "Shell Entity" in scenario_preset:
        def_inv_amt, def_txn_amt = 500000.0, 500000.0
        def_carrier = "None"
        def_hours_to_pay = 12.0
        def_hist_fraud = 8
        def_is_night = True

    with col_ctrl1:
        inv_amt = st.number_input("Invoice Face Value ($)", min_value=1000.0, max_value=5000000.0, value=def_inv_amt, step=5000.0)
        txn_amt = st.number_input("Settlement Payment Amount ($)", min_value=1000.0, max_value=5000000.0, value=def_txn_amt, step=5000.0)
        carrier_opt = st.selectbox("Logistics Carrier:", ["DHL Global Express", "FedEx International", "Maersk Ocean Freight", "None"], index=0 if def_carrier != "None" else 3)

    with col_ctrl2:
        hours_pay = st.number_input("Payment Delay After Invoice (Hours):", min_value=0.5, max_value=2500.0, value=def_hours_to_pay, step=10.0)
        fraud_hist = st.slider("Supplier Prior Fraud Count:", min_value=0, max_value=10, value=def_hist_fraud)
        is_night = st.checkbox("Nighttime Off-Hours Settlement (00:00 - 05:00 UTC)", value=def_is_night)

    if st.button("🚀 Run Live AI Risk Inference & SHAP Attribution", type="primary"):
        now = datetime.now(timezone.utc)
        inv_date = now - pd.Timedelta(hours=hours_pay)
        ship_date = inv_date + pd.Timedelta(hours=48) if carrier_opt != "None" else None

        test_data = {
            "invoice_amount": inv_amt,
            "transaction_amount": txn_amt,
            "carrier": carrier_opt,
            "supplier_id": "SUPP-TEST-LAB",
            "buyer_id": "BUYER-TEST-LAB",
            "invoice_date": inv_date,
            "shipment_date": ship_date,
            "payment_date": now,
            "supplier_fraud_history": fraud_hist,
            "amount_to_supplier_avg_ratio": txn_amt / (inv_amt + 1e-5),
        }

        # Run inference and SHAP attribution
        with st.spinner("Executing XGBoost inference and computing TreeExplainer SHAP values..."):
            pred = predict_transaction_risk(test_data)
            explanation = explain_transaction_risk(test_data)

        st.markdown("---")
        st.subheader("Inference Results")

        res1, res2, res3 = st.columns(3)
        with res1:
            color = "#EF4444" if pred["risk_level"] == "HIGH" else ("#F59E0B" if pred["risk_level"] == "MEDIUM" else "#10B981")
            st.metric("Fraud Probability Score", f"{pred['fraud_probability']:.1%}")
            st.markdown(f"**Classification:** <span style='color:{color}; font-weight:700;'>{pred['risk_level']} RISK</span>", unsafe_allow_html=True)
        with res2:
            st.metric("Credit Default Risk", f"{pred['default_probability']:.1%}")
            st.markdown(f"**Action:** `{pred['action_label']}`")
        with res3:
            st.metric("Model Architecture", "XGBoost (Class-Balanced)")
            st.markdown(f"**Model Version:** `{pred['model_version']}`")

        # Plotly horizontal bar chart of SHAP values
        p_data = explanation["plot_data"]
        fig_bar = go.Figure(go.Bar(
            x=p_data["shap_values"],
            y=p_data["features"],
            orientation="h",
            marker_color=p_data["colors"]
        ))
        fig_bar.update_layout(
            title="Local SHAP Feature Contributions (+ Contributes to Fraud, - Mitigates Fraud)",
            template="plotly_dark",
            height=320,
            margin=dict(l=20, r=20, t=40, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("#### Auditor Explanation Summary")
        st.code(explanation["summary_text"], language="text")


# =========================================================================
# PAGE 6: BLOCKCHAIN EXPLORER & EVENT LOGS
# =========================================================================

elif menu_selection == "⛓️ Blockchain Explorer":
    render_header(
        "Cryptographic Blockchain Explorer",
        "Immutable ledger blocks and smart contract event logs (InvoiceCreated, ShipmentConfirmed, PaymentReleased)."
    )

    # Simulator trigger for interactive live demo
    with st.expander("⚡ Live Demo Tool: Simulate New On-Chain Transaction", expanded=False):
        st.markdown("Emit a new supply chain event directly to the simulated ledger and verify automated SQL/AI pipeline execution:")
        sim_col1, sim_col2 = st.columns(2)
        with sim_col1:
            new_inv_id = st.text_input("New Invoice ID", value=f"INV-LIVE-{np.random.randint(100, 999)}")
            new_amt = st.number_input("Invoice Amount ($)", value=98000.0, step=5000.0)
            new_supp = st.selectbox("Supplier", ["SUPP-GLOBAL-01", "SUPP-NEXUS-02", "SUPP-SUSP-04"])
        with sim_col2:
            new_buyer = st.selectbox("Buyer", ["BUYER-OMEGA-01", "BUYER-VORTEX-02", "BUYER-QUICK-03"])
            new_desc = st.text_input("Description", value="Cryogenic Actuator Batch")
            do_ship = st.checkbox("Include Physical Shipment Dispatch", value=True)

        if st.button("🚀 Emit On-Chain Events & Ingest to SQL", type="primary"):
            # 1. InvoiceCreated
            evt1 = simulator.simulate_invoice_creation(
                invoice_id=new_inv_id,
                supplier_id=new_supp,
                buyer_id=new_buyer,
                amount=new_amt,
                item_description=new_desc,
                supplier_wallet="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                buyer_wallet="0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"
            )
            # 2. Shipment if checked
            if do_ship:
                simulator.simulate_shipment_confirmation(
                    invoice_id=new_inv_id,
                    carrier="DHL Global Express",
                    tracking_number=f"DHL-{np.random.randint(100000, 999999)}",
                    supplier_wallet="0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
                )
            st.success(f"Emitted on-chain events on Block #{evt1['block_number']}! Tx Hash: {evt1['tx_hash']}")
            st.rerun()

    events = db.get_recent_blockchain_events(limit=50)
    if events:
        df_evts = pd.DataFrame(events)
        st.markdown(f"**Latest {len(df_evts)} Verified Blockchain Transactions:**")
        st.dataframe(
            df_evts[[
                "block_number", "transaction_type", "invoice_id", "amount",
                "blockchain_tx_hash", "sender_address", "timestamp"
            ]],
            use_container_width=True,
            height=500
        )
    else:
        st.info("No blockchain events recorded.")
