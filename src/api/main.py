"""FastAPI service for customer recommendations.

Run locally:
    uv run uvicorn src.api.main.py --reload
    
Then open http://localhost:8000/docs for the auto-generated API documentation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Query

from ..ml import config, recommender
from .deps import AppState, get_state, lifespan
from .schemas import (
    ChurnRiskResponse,
    CrossSellResponse,
    HealthResponse,
    ProductRecommendation,
    RecommendationResponse,
    TopCustomersResponse
)

app = FastAPI(
    title="UCI Online Retail - Customer Recommendation API",
    description=(
        "Serves CLV predictions, churn risk, and personalized "
        "recommendations for the UCI Online Retail dataset."
    ),
    version="0.1.0",
    lifespan=lifespan
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get('/health', response_model=HealthResponse, tags=['meta'])
def health(state: AppState = Depends(get_state)):
    """Cheap endpoint for uptime monitors and load balancer health checks."""
    return HealthResponse(
        status='ok',
        n_customers=len(state.customers),
        models_loaded=['clv_xgboost','churn_xgboost'],
    )
    
    
# ---------------------------------------------------------------------------
# Customer endpoints
# ---------------------------------------------------------------------------
def _build_full_recommendation(customer_id: str, state: AppState) -> dict:
    """Shared helper: assemble the full recommendation record for one customer."""
    matches = state.customers[state.customers['CustomerID'] == customer_id]
    if matches.empty:
        raise HTTPException(404, f'Customer {customer_id} not found')
    
    customer_row = matches.iloc[0]
    row_idx = matches.index[0]
    
    predicted_clv = float(customer_row['predicted_clv_90d'])
    churn_risk = float(customer_row['churn_risk'])
    quadrant = recommender.assign_strategy_quadrant(
        predicted_clv, churn_risk, state.clv_threshold
    )
    
    # SHAP-driven churn drivers
    feat_row = state.feature_matrix.iloc[row_idx]
    # The explainer expect a 2D array - wrap the single row.
    shap_values = state.churn_explainer.shap_values(
        feat_row.values.reshape(1, -1)
    )[0]
    drivers = recommender.top_churn_drivers(
        shap_values, feat_row, state.churn.feature_names, top_n=3
    )
    
    # Anchor product + cross-sell recommendations
    anchor = None
    cross_sell = []
    if not state.customer_top_product.empty and customer_id in state.customer_top_product.index:
        top_row = state.customer_top_product.loc[customer_id]
        anchor_code = top_row.get('top_product_code')
        anchor = {
            'code': str(anchor_code) if pd.notna(anchor_code) else None,
            'description': str(top_row.get('top_product_desc'))
            if pd.notna(top_row.get('top_product_desc')) else None,
        }
        if anchor_code in state.cross_sell_lookup:
            cross_sell = [
                {
                    'code': p['recommendation_code'],
                    'description': p['recommendation_description'],
                    'lift': round(float(p['lift']), 2),
                }
                for p in state.cross_sell_lookup[anchor_code][:3]
            ]
            
    return recommender.build_recommendation(
        customer_row=customer_row,
        predicted_clv=predicted_clv,
        churn_risk=churn_risk,
        strategy_quadrant=quadrant,
        churn_drivers=drivers,
        cross_sell_products=cross_sell,
        anchor_product=anchor,
    )


@app.get(
    '/customers/{customer_id}/recommendation',
    response_model=RecommendationResponse,
    tags=['customers'],
    summary='Full recommendation for one customer',
)
def get_customer_recommendation(
    customer_id: str, state: AppState = Depends(get_state)
):
    """Returns the complete record: segment, CLV, churn risk, action playbook,
    SHAP-driven explanations, and cross-sell product recommendations."""
    return _build_full_recommendation(customer_id, state)


@app.get(
    '/customers/{customer_id}/risk',
    response_model=ChurnRiskResponse,
    tags=['customers'],
    summary='Lightweight churn risk + top drivers',
)
def get_customer_risk(customer_id: str, state: AppState = Depends(get_state)):
    """Faster than '/recommendation' - only churn risk + top driver features.
    Use this when you don't need the full product recommendations.
    """
    matches = state.customers[state.customers['CustomerID'] == customer_id]
    if matches.empty:
        raise HTTPException(404, f'Customer {customer_id} not found.')
    
    customer_row = matches.iloc[0]
    row_idx = matches.index[0]
    churn_risk = float(customer_row['churn_risk'])
    
    feat_row = state.feature_matrix.iloc[row_idx]
    shap_values = state.churn_explainer.shap_values(
        feat_row.values.reshape(1, -1)
    )[0]
    drivers = recommender.top_churn_drivers(
        shap_values, feat_row, state.churn.feature_names, top_n=5
    )
    
    return ChurnRiskResponse(
        customer_id=customer_id,
        churn_risk=churn_risk,
        p_active=1.0 - churn_risk,
        top_drivers=drivers
    )
    
    
@app.get(
    '/customers/top',
    response_model=TopCustomersResponse,
    tags=['customers'],
    summary="Marketing team's worklist - top N customers by priority",
)
def get_top_customers(
    n: int = Query(20, ge=1, le=500, description="How many to return"),
    quadrant: str | None = Query(None, description="Optional filter by strategy quadrant"),
    state: AppState = Depends(get_state),
):
    """Returns the highest-priority customers for marketing intervention.
    By default uses the quadrant-tiered ranking from Notebook 08 Option B:
    Urgent Win-back -> VIP Retention -> Upsell Opportunity -> Low Priority.
    """
    df = state.customers.copy()
    df['strategy_quadrant'] = df.apply(
        lambda r: recommender.assign_strategy_quadrant(
            r['predicted_clv_90d'], r['churn_risk'], state.clv_threshold
        ),
        axis=1
    )
    if quadrant is not None:
        df = df[df['strategy_quadrant'] == quadrant]
        if df.empty:
            return TopCustomersResponse(n_returned=0, customers=[])
        
    df['intervention_cost'] = df['strategy_quadrant'].map(
        lambda q: config.ACTION_PLAYBOOK.get(q, {}).get('intervention_cost_gbp', 0)
    )
    df['priority'] = df.apply(
        lambda r: recommender.priority_score(
            r['strategy_quadrant'], r['churn_risk'],
            r['predicted_clv_90d'], r['intervention_cost']
        ),
        axis=1,
    )
    
    top = df.nlargest(n, 'priority')
    recs = [_build_full_recommendation(str(cid), state) for cid in top['CustomerID']]
    return TopCustomersResponse(n_returned=len(recs), customers=recs)


# ---------------------------------------------------------------------------
# Product endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/products/{product_code}/cross_sell",
    response_model=CrossSellResponse,
    tags=["products"],
    summary="Top products frequently bought with this one",
)
def get_product_cross_sell(
    product_code: str,
    n: int = Query(5, ge=1, le=20),
    state: AppState = Depends(get_state),
):
    """Returns the top N cross-sell recommendations for a given product,
    ranked by 'lift'. Uses the Apriori rules from Notebook 07."""
    recs_raw = state.cross_sell_lookup.get(product_code)
    if not recs_raw:
        raise HTTPException(
            404,
            f"No cross-sell rules founds for product {product_code}. "
            "Only ~30 popular products have rules - see Notebook 07.",
        )
    recs = [
        ProductRecommendation(
            code=p["recommendation_code"],
            description=p["recommendation_description"],
            lift=round(float(p["lift"]), 2),
        ) for p in recs_raw[:n]
    ]
    return CrossSellResponse(product_code=product_code, recommendations=recs)