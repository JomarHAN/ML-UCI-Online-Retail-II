"""API integration tests.

Uses FastAPI's TestClient - boots the app in-process, send real HTTP requests
to it, validates responses. Catches problems that unit tests miss:
    - Schema serialization errors
    - Wrong status codes
    - Missing dependencies
    - Lifespan startup failures
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.main import app


@pytest.fixture(scope="module")
def client():
    """One TestClient per test module. The `with` block triggers lifespan
    (startup loads models), then teardown when module finishes."""
    with TestClient(app) as c:
        yield c
        
        
@pytest.fixture(scope="module")
def known_customer_id(client):
    """A real CustomerID from the loaded data, for tests that need one."""
    response = client.get("/customers/top", params={"n": 1})
    assert response.status_code == 200
    return response.json()["customers"][0]["customer_id"]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["n_customers"] > 0
    assert "clv_xgboost" in body["models_loaded"]
    assert "churn_xgboost" in body["models_loaded"]
    
    
# ---------------------------------------------------------------------------
# Customer endpoints
# ---------------------------------------------------------------------------
def test_get_recommendation_known_customer(client, known_customer_id):
    r = client.get(f"/customers/{known_customer_id}/recommendation")
    assert r.status_code == 200
    body = r.json()
    
    # Shape check -  the schema enforces this, but explicit check fail loud
    assert body["customer_id"] == known_customer_id
    assert "segment" in body
    assert "strategy_quadrant" in body
    assert 0 <= body["metrics"]["churn_risk"] <= 1
    assert body["metrics"]["predicted_clv_90d_gbp"] >= 0
    assert isinstance(body["churn_drivers"], list)
    assert isinstance(body["recommended_products"], list)
    

def test_get_recommendation_unknown_customer(client):
    r = client.get("/customers/not-a-real-id/recommendation")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()
    
    
def test_get_risk_known_customer(client, known_customer_id):
    r = client.get(f"/customers/{known_customer_id}/risk")
    assert r.status_code == 200
    body = r.json()
    assert body["customer_id"] == known_customer_id
    # p_active and churn_risk should sum to 1
    assert abs((body["churn_risk"] + body["p_active"]) - 1.0) < 1e-6
    

def test_get_risk_unknown_customer(client):
    r = client.get("/customers/not-a-real-id/risk")
    assert r.status_code == 404
    
    
def test_top_customers_default(client):
    r = client.get("/customers/top")
    assert r.status_code == 200
    body = r.json()
    assert body["n_returned"] == 20     # default
    assert len(body["customers"]) == 20
    # should be sorted descending by priority
    priorities = [c["priority_score"] for c in body["customers"]]
    assert priorities == sorted(priorities, reverse=True)
    
    
def test_top_customers_custom_n(client):
    r = client.get("/customers/top", params={"n": 5})
    assert r.status_code == 200
    assert r.json()["n_returned"] == 5
    
    
def test_top_customers_filtered_by_quadrant(client):
    r = client.get("/customers/top", params={"quadrant": "2. Urgent Win-back", "n": 10})
    assert r.status_code == 200
    body = r.json()
    # All returned customers should be in the specified quadrant
    assert all(
        c["strategy_quadrant"] == "2. Urgent Win-back"
        for c in body["customers"]
    )
    
    
def test_top_customers_invalid_n(client):
    r = client.get("/customers/top", params={"n": 0})
    assert r.status_code == 422
    
    
# ---------------------------------------------------------------------------
# Product endpoints
# ---------------------------------------------------------------------------
def test_cross_sell_known_product(client):
    """Pick the first product code that has rules and hit the endpoint"""
    from src.api.deps import state
    # We need lifespan to have run, which the client fixture ensures
    assert state is not None
    if not state.cross_sell_lookup:
        pytest.skip("No cross-sell rules loaded")
    product_code = next(iter(state.cross_sell_lookup))
    r = client.get(f"/products/{product_code}/cross_sell")
    assert r.status_code == 200
    body = r.json()
    assert body["product_code"] == product_code
    assert len(body["recommendations"]) > 0
    assert all(rec["lift"] > 1 for rec in body["recommendations"])  # all rules have lift > 1.5
    
    
def test_cross_sell_unknown_product(client):
    r = client.get("/products/NOTAREALCODE/cross_sell")
    assert r.status_code == 404
    
    
# ---------------------------------------------------------------------------
# OpenAPI docs
# ---------------------------------------------------------------------------
def test_openapi_docs_available(client):
    """FastAPI auto-generates '/docs' and '/openapi.json' . Verify they work."""
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200