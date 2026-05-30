"""Pydantic schema for the API

Pydantic does three things at once:
1. **Validates** incoming requests (rejects bad input with a clear error)
2. **Serializes** outgoing responses (turn Python objects into JSON safely)
3. **Documents** the API automatically (FastAPI generates OpenAPI docs from these)

Every endpoint should have a request model (if it takes a body) and a response model.
The response model also acts as the contract - anything not in the model is stripped
from the response, so we can't accidentally leak internal fields.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=['ok'])
    n_customers: int
    models_loaded: list[str]
    
    
class ChurnDriver(BaseModel):
    feature: str
    value: float | bool | str
    shap_impact: float
    
    
class ProductRecommendation(BaseModel):
    code: str
    description: str
    lift: float
    
    
class AnchorProduct(BaseModel):
    code: str | None
    description: str | None
    

class CustomerMetrics(BaseModel):
    historical_revenue_gbp: float
    predicted_clv_90d_gbp: float
    churn_risk: float = Field(..., ge=0.0, le=1.0)
    recency_days: int
    order_frequency: int
    
    
class CustomerAction(BaseModel):
    name: str
    tactic: str
    urgency: str
    recommended_discount_pct: int
    intervention_cost_gbp: float
    
    
class RecommendationResponse(BaseModel):
    customer_id: str
    segment: str
    strategy_quadrant: str
    priority_score: float
    metrics: CustomerMetrics
    action: CustomerAction
    churn_drivers: list[ChurnDriver]
    recommended_products: list[ProductRecommendation]
    anchor_product: AnchorProduct
    
    
class ChurnRiskResponse(BaseModel):
    """Lightweight subset for the/risk endpoint."""
    customer_id: str
    churn_risk: float = Field(..., ge=0.0, le=1.0)
    p_active: float = Field(..., ge=0.0, le=1.0)
    top_drivers: list[ChurnDriver]
    
    
class CrossSellResponse(BaseModel):
    product_code: str
    recommendations: list[ProductRecommendation]
    
    
class TopCustomersResponse(BaseModel):
    """The marketing team's daily worklist."""
    n_returned: int
    customers: list[RecommendationResponse]
    
    
class ErrorResponse(BaseModel):
    detail: str
    