"""Build per-customer recommendations.
Extracted from Notebook 08. The Notebook's 'Option B' quadrant-tiered priority
is used (so Urget Win-back ranks above VIP Retention, regardless of CLV magnitude).
This module is intentionally stateless: every function takes data + models in
and returns plain dicts/dataframes out. The API layer wraps it in HTTP.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap

from . import config


def assign_strategy_quadrant(
    predicted_clv: float, churn_risk: float, clv_threshold: float
) -> str:
    """Map (CLV, churn risk) to one of the four strategy quadrants."""
    high_clv = predicted_clv >= clv_threshold
    high_risk = churn_risk >= config.CHURN_RISK_THRESHOLD
    if high_clv and not high_risk:
        return '1. VIP Retention'
    if high_clv and high_risk:
        return '2. Urget Win-back'
    if not high_clv and not high_risk:
        return '3. Upsell Opportunity'
    return '4. Low Priority'


def priority_score(
    quadrant: str, churn_risk: float, predicted_clv: float, intervention_cost: float
) -> float:
    """Quadrant-tiered priority. Higher = contact first
    Matches the Notebook 08 'Option B' fix: a giant quadrant multiplier ensures
    Urgent Win-back outranks VIP Retention; within a quadrant, expected
    intervention value is the tiebreaker.
    """
    tier = config.QUADRANT_PRIORITY.get(quadrant, 0)
    within = churn_risk * predicted_clv - intervention_cost
    return tier * 10_000 + within


def top_churn_drivers(
    shap_row: np.ndarray, feature_values: pd.Series, feature_names: list[str], top_n: int = 3
) -> list[dict[str, Any]]:
    """Return the top N features pushing this customer toward churn.
    Negative SHAP = pushed toward churn (since target=1 means active)
    """
    order = np.argsort(shap_row)[:top_n]
    drivers = []
    for i in order:
        shap_value = float(shap_row[i])
        if shap_value >= 0:
            continue    # not actually pushing toward churn
        feat_value = feature_values.iloc[i]
        # Coerce numpy types to JSON-friendly primitives
        if isinstance(feat_value, (bool, np.bool_)):
            safe_value: Any = bool(feat_value)
        elif isinstance(feat_value, (int, float, np.integer, np.floating)):
            safe_value = float(feat_value)
        else:
            safe_value = str(feat_value)
        drivers.append(
            {'feature': feature_names[i], 'value': safe_value, 'shap_impact': shap_value}
        )
    return drivers


def build_recommendation(
    customer_row: pd.Series,
    predicted_clv: float, 
    churn_risk: float,
    strategy_quadrant: str,
    churn_drivers: list[dict],
    cross_sell_products: list[dict],
    anchor_product: dict | None = None
) -> dict[str, Any]:
    """Assemble all signals into one recommendation record.
    This is the shape the API will return - keep it stable.
    """
    playbook = config.ACTION_PLAYBOOK.get(strategy_quadrant, {})
    intervention_cost = playbook.get('intervention_cost_gbp', 0)
    
    return {
        'customer_id': str(customer_row['CustomerID']),
        'segment': str(customer_row.get('segment','Unknown')),
        'strategy_quadrant': strategy_quadrant,
        'priority_score': round(
            priority_score(strategy_quadrant, churn_risk, predicted_clv, intervention_cost), 3
        ),
        'metrics': {
            'historical_revenue_gbp': round(float(customer_row.get('monetary', 0)), 2),
            'predicted_clv_90d_gbp': round(float(predicted_clv), 2),
            'churn_risk': round(float(churn_risk), 3),
            'recency_days': int(customer_row.get('recency_days', 0)),
            'order_frequency': int(customer_row.get('frequency', 0)),
        },
        'action': {
            'name': playbook.get('action_name', ''),
            'tactic': playbook.get('tactic', ''),
            'urgency': playbook.get('urgency', ''),
            'recommended_discount_pct': playbook.get('discount_pct', 0),
            'intervention_cost_gbp': intervention_cost,
        },
        'churn_drivers': churn_drivers,
        'recommended_products': cross_sell_products,
        'anchor_product': anchor_product or {'code': None, 'description': None},
    }
    
    
def load_cross_sell_lookup(parquet_path) -> dict[str, list[dict]]:
    """Load the product cross-sell rules into a dict for 0(1) lookup."""
    try:
        cross_sell = pd.read_parquet(parquet_path)
    except FileNotFoundError:
        return {}
    
    return (
        cross_sell.groupby('product_code')
        .apply(
            lambda g: g[['recommendation_code', 'recommendation_description', 'lift']]
            .to_dict(orient='records')
        )
        .to_dict()
    )
    
    
def compute_clv_threshold(predictions: pd.Series) -> float:
    """The data-dependent CLV cutoff for high vs low (median by default)."""
    return float(predictions.quantile(0.50))


def get_shap_expalainer(model):
    """Build a SHAP explainer for a tree model. Used once per service startup."""
    return shap.TreeExplainer(model)