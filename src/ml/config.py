"""Central configuration for the UCI Online Retail ML Pipeline.
Everything that was a magic number or hardcoded string scattered across the 
notobook lives here, so there is exactly one place to change it. Training and
serving both import from this module, which is how we guarantee they agree."""

from __future__ import annotations

from pathlib import Path

# -----------------------
# Paths
# -----------------------
# PROJECT_ROOT resolves to the repo root regardless of where code is run from.
# config.py is at <root>/src/ml/config.py, so go up three levels
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR  = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

RAW_CSV = RAW_DIR / "online_retail_II.csv"

# -----------------------------------
# Cleaning constants (from Notebook 02)
# -----------------------------------
# StockCodes that are not real products (postage, fees, adjustments, tests)
NON_PRODUCT_CODES: frozenset[str] = frozenset({
    'POST', 'DOT', 'M', 'BANK CHARGES', 'AMAZONFEE',
    'D', 'C2', 'PADS', 'CRUK', 'B',
    'TEST001', 'TEST002', 'S', 'ADJUST'
})

# Descriptions that are warehouse annotations, not products (from Notebook 02 investigation - these survive price/quantity filters when price > 0)
ADMIN_DESCRIPTIONS: frozenset[str] = frozenset({
    'CHECK', 'DAMAGED', 'MISSING', 'LOST', 'BROKEN', 
    'WET', 'WATER DAMAGED', 'AMAZON', 'EBAY', 'UPDATE', 
    'MAILOUT', 'SAMPLES', 'SOLD AS SET ON DOTCOM', 'SOLD AS 1',
    'FOUND', 'FAULTY', 'ADJUSTMENT', 'RETURNED',
    'SMASHED', 'CRACKED', 'THROWN AWAY', 'TEST'
})

# Flag (not drop) orders with quantity at or above this as bulk/wholesale.
BULK_ORDER_QUANTITY_THRESHOLD = 1000

# -----------------------------------
# Feature engineering constants (from Notebook 03)
# -----------------------------------
# How many days after the snapshot we look to define the prediction target.
TARGET_WINDOW_DAYS = 90

# Small epsilon added to denominators to avoid divide-by-zero in ratios
RATIO_EPSILON = 0.01

# -----------------------------------
# Columns the models were trained to exclude (from Notebook 05/06)
# -----------------------------------
# Non-feature columns: identifiers, raw categoricals already encoded, targets
EXCLUDE_FROM_FEATURES: frozenset[str] = frozenset({
    'CustomerID', 'primary_country', 'RFM_score', 'cluster_name',
    'target_revenue_90d', 'target_orders_90d', 'target_purchased_90d'
})

# Target column names
TARGET_REVENUE = 'target_revenue_90d'
TARGET_ORDERS = 'target_orders_90d'
TARGET_PURCHASED = 'target_purchased_90d'

# -----------------------------------
# Model artifact filenames
# -----------------------------------
CLV_MODEL_FILE = MODELS_DIR / 'clv_xgboost.joblib'
CHURN_MODEL_FILE = MODELS_DIR / 'churn_xgboost.joblib'

# -----------------------------------
# Strategy quadrant definitions (from Notebook 06)
# -----------------------------------
CHURN_RISK_THRESHOLD = 0.50     # above this = "high churn risk"
# CLV threshold is data-dependent (median); computed at runtime, not fixed here.

# Quadrant priority tiers (from the Notebook 08 Option B fix).
QUADRANT_PRIORITY = {
    "2. Urgent Win-back": 4,
    "1. VIP Retention": 3,
    "3. Upsell Opportunity": 2,
    "4. Low Priority": 1,
}

# -----------------------------------
# Action playbook (from Notebook 08)
# -----------------------------------
ACTION_PLAYBOOK = {
    "1. VIP Retention": {
        "action_name": "Reward & retain",
        "tactic": "Invite to loyalty program; early access to new arrivals",
        "discount_pct": 0,
        "urgency": "low",
        "intervention_cost_gbp": 5,
    },
    "2. Urgent Win-back":{
        "action_name": "Urgent personalized win-back",
        "tactic": "Personal email + meaningful discount on a previously-loved category",
        "discount_pct": 15,
        "urgency": "high",
        "intervention_cost_gbp": 20,
    },
    "3. Upsell Opportunity":{
        "action_name": "Cross-sell to grow basket",
        "tactic": "Recommend complementaty products at checkout/email",
        "discount_pct": 5,
        "urgency": "medium",
        "intervention_cost_gbp": 3,
    },
    "4. Low Priority":{
        "action_name": "Minimal investment",
        "tactic": "Generic newsletter only",
        "discount_pct": 0,
        "urgency": "low",
        "intervention_cost_gbp": 0.5
    }
}