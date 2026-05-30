# UCI Online Retail Analytics

A data science and ML engineering project for customer analytics and recommendations using the UCI Online Retail dataset. The repository includes raw and processed data, exploratory notebooks, trained machine learning artifacts, a reusable Python package, and a FastAPI service that exposes the models over HTTP.

## Overview

This project analyzes retail transaction data to build customer-level insights, including:

- customer lifetime value (CLV) prediction
- churn risk modeling
- customer segmentation and feature engineering
- product recommendation generation
- a production-style API serving these predictions and recommendations

The workflow is notebook-driven for analysis and modeling, with reusable artifacts saved in `models/` and processed datasets in `data/processed/`. The notebook code has been refactored into a reusable `src/ml/` package, and a FastAPI application in `src/api/` makes the models available as HTTP endpoints.

## Technical Architecture

The repository follows a modular analysis and serving pipeline:

1. **Data ingestion**
   - Raw data is stored in `data/raw/online_retail_II.csv`
   - Interim and processed datasets are stored under `data/interim/` and `data/processed/`

2. **Exploration and cleaning**
   - Jupyter notebooks explore dataset quality, describe customer behavior, and perform cleansing.

3. **Feature engineering**
   - Customer features are derived from transactional history, frequency, recency, monetary value, and purchase behavior.
   - Feature logic lives in `src/ml/features.py` and is used identically during training (batch) and serving (single customer), preventing training-serving skew.

4. **Modeling**
   - XGBoost models are trained for churn and CLV prediction.
   - Saved model artifacts are stored in `models/churn_xgboost.joblib` and `models/clv_xgboost.joblib`.

5. **Recommendation generation**
   - Product recommendations and metadata are stored in `data/processed/recommendations.jsonl` and `data/processed/customer_features_metadata.json`.
   - The recommendation assembly logic lives in `src/ml/recommender.py`.

6. **API serving**
   - A FastAPI application in `src/api/` loads the trained models at startup and exposes endpoints for customer recommendations, churn risk, and product cross-sell rules.
   - Auto-generated interactive API documentation is available at `/docs`.

7. **Presentation and outputs**
   - Notebooks produce figures, tables, and example outputs collected in `reports/figures/`.

## Installation

### Requirements

- Python 3.12 or newer
- [`uv`](https://github.com/astral-sh/uv) for dependency management (recommended), or `pip`

### Install dependencies with uv (recommended)

From the repository root:

```bash
uv sync
```

This creates a `.venv/` and installs all dependencies pinned in `uv.lock`. To include development dependencies (pytest, jupyter, etc.):

```bash
uv sync --extra dev
```

### Install with pip (alternative)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -e .[dev]   # for dev dependencies
```

## Usage

### Run the notebooks

```bash
uv run jupyter lab
```

Then open notebooks under `notebooks/` in order (01 → 08).

### Run the API locally

Start the FastAPI service:

```bash
uv run uvicorn src.api.main:app --reload
```

The API will be available at http://localhost:8000. Open http://localhost:8000/docs for the interactive Swagger UI where you can try every endpoint from the browser.

Example requests:

```bash
# Health check
curl http://localhost:8000/health

# Top 5 highest-priority customers (marketing team's worklist)
curl "http://localhost:8000/customers/top?n=5"

# Full recommendation for a specific customer
curl http://localhost:8000/customers/12454.0/recommendation

# Lightweight churn risk for a customer
curl http://localhost:8000/customers/12454.0/risk

# Filter top customers by strategy quadrant
curl "http://localhost:8000/customers/top?quadrant=2.+Urgent+Win-back&n=10"

# Cross-sell recommendations for a product
curl http://localhost:8000/products/85099B/cross_sell
```

### Run the tests

```bash
uv run pytest tests/ -v
```

The suite includes 10 unit/integration tests for the ML modules (including a critical training-serving consistency test) and 12 integration tests for the API.

### Run the package entrypoint

```bash
python main.py
```

This prints a simple message from the package. The primary project work is in the notebooks and the API.

## Detailed Breakdown

This section explains each top-level file, data artifact, and notebook: what was done, why it was done, and the business meaning of each action.

### Repository Root
- **`main.py`**: minimal entrypoint that prints a greeting. Created as a smoke test to verify packaging and environment setup before running the heavier analysis notebooks. Business meaning: quick sanity check for collaborators and CI.
- **`pyproject.toml`**: project metadata and dependency constraints. Versions and caps (e.g., `numpy<2.4`, `llvmlite==0.45`) were chosen to avoid platform wheel issues and to ensure reproducible analysis. Business meaning: stability and reproducibility for development and deployment.
- **`README.md`**: project overview, architecture, and usage instructions (this file). Documenting the project accelerates onboarding and stakeholder understanding.

### Data
- **`data/raw/online_retail_II.csv`**: immutable source-of-truth transaction data. Keeping raw files unchanged preserves auditability.
- **`data/interim/`**: intermediate processing outputs used to speed iterative experimentation and avoid re-running expensive steps.
- **`data/processed/`**: final feature datasets and exported outputs such as `customer_features_metadata.json` and `recommendations.jsonl` used by downstream systems.

### Models
- **`models/churn_xgboost.joblib`** and **`models/clv_xgboost.joblib`**: serialized model artifacts produced from the notebooks. Joblib was selected for fast load/save in Python. Each artifact stores the trained model alongside its feature names and chosen decision threshold so the API can reproduce training-time behavior exactly. Business meaning: these artifacts power operational predictions (churn prioritization, CLV-driven budgeting).

### Notebooks (detailed)
Each notebook contains a self-contained stage of the analysis pipeline. Below is a concise mapping of the typical actions performed and why, plus the business interpretation.

- **`notebooks/01_EDA.ipynb`** — Exploratory Data Analysis
   - What: data loading, descriptive stats, missingness checks, top-SKU/customer summaries, time-series views.
   - Why: understand data quality, seasonality, and anomalies before modeling.
   - Business meaning: identifies operational issues and business patterns (peak periods, problem SKUs).

- **`notebooks/02_cleaning.ipynb`** — Data Cleaning
   - What: deduplication, timestamp parsing, handling returns/refunds and invalid transactions.
   - Why: ensure training data is accurate and unbiased.
   - Business meaning: preserves trust in model outputs and downstream decisions.

- **`notebooks/03_feature_engineering.ipynb`** — Feature Generation
   - What: customer-level aggregates (RFM), time-windowed features, behavioral flags, product affinity counts.
   - Why: provide informative predictors capturing customer value and behavior.
   - Business meaning: features enable effective segmentation, scoring, and campaign targeting.

- **`notebooks/04_segmentation.ipynb`** — Customer Segmentation
   - What: RFM scoring with quintile-based segments, K-Means clustering as a cross-check, action playbook per segment.
   - Why: group customers with similar lifetime value and behavior.
   - Business meaning: drives targeted marketing, merchandising, and retention strategies.

- **`notebooks/05_clv_prediction.ipynb`** — CLV Modeling
   - What: train/validate XGBoost regressor for Customer Lifetime Value with log-transformed target; evaluate with lift chart and SHAP explanations; save `clv_xgboost.joblib`.
   - Why: estimate future monetary value to inform acquisition and retention ROI.
   - Business meaning: informs budget allocation and customer prioritization.

- **`notebooks/06_churn_prediction.ipynb`** — Churn Risk Modeling
   - What: train XGBoost classifier for 90-day churn risk, threshold selection sweep, calibration check, combine with CLV to produce the 2×2 strategy matrix.
   - Why: identify at-risk customers for targeted interventions.
   - Business meaning: reduces churn-driven revenue loss through prioritized retention campaigns.

- **`notebooks/07_market_basket.ipynb`** — Market-Basket Analysis
   - What: Apriori frequent itemsets, association rules ranked by lift, per-product cross-sell lookup table.
   - Why: discover product affinities for cross-sell and bundling.
   - Business meaning: increases average order value and improves promotion effectiveness.

- **`notebooks/08_recommendations.ipynb`** — Recommendation Assembly
   - What: combine segment, CLV, churn risk, SHAP drivers, and cross-sell rules into one record per customer; quadrant-tiered priority ranking; export to JSONL.
   - Why: produce personalized recommendations ready for ingestion by marketing or product systems.
   - Business meaning: directly impacts conversions and personalization-driven revenue uplift.

### Source package and code layout

The notebook logic has been refactored into a reusable Python package under `src/`:

#### `src/ml/` — Machine learning modules

- **`config.py`**: single source of truth for paths, constants, feature exclusion lists, the cleaning rules, the action playbook, and quadrant priorities. Changing a constant in one place propagates to both training and serving.
- **`cleaning.py`**: extracted from Notebook 02 as composable, individually testable functions (`split_cancellations`, `drop_non_product_codes`, `normalize_text`, etc.) chained in `clean_transactions`.
- **`features.py`**: the most important module. `build_customer_features(transactions, snapshot_date, cancellations)` produces a feature row per customer using only data on or before the snapshot date. The same function is used for batch training and single-customer serving — this is the structural guarantee against training-serving skew.
- **`segmentation.py`**: RFM scoring with `.rank(method='first')` tie-breaking on all three dimensions, plus segment assignment rules from Notebook 04.
- **`models.py`**: `CLVPredictor` and `ChurnPredictor` classes wrap the joblib artifacts, align incoming feature frames to the trained column order, and expose clean `predict` methods.
- **`recommender.py`**: assembles signals into per-customer recommendation records, computes the quadrant-tiered priority score, and extracts the top SHAP-based churn drivers.

#### `src/api/` — FastAPI service

- **`schemas.py`**: Pydantic models that validate incoming requests, serialize outgoing responses, and automatically generate the OpenAPI specification.
- **`deps.py`**: application lifespan management. Loads trained models, feature matrix, SHAP explainer, and lookup tables once at startup so request-time latency stays low.
- **`main.py`**: the FastAPI application and its seven endpoints (see below).

### API endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check for load balancers and monitors |
| `GET` | `/customers/{id}/recommendation` | Full recommendation record for one customer |
| `GET` | `/customers/{id}/risk` | Lightweight churn risk + top SHAP drivers |
| `GET` | `/customers/top` | Marketing team's worklist, top N by priority (optional quadrant filter) |
| `GET` | `/products/{code}/cross_sell` | Top cross-sell rules for a product |
| `GET` | `/openapi.json` | Auto-generated OpenAPI specification |
| `GET` | `/docs` | Interactive Swagger UI |

### Reports and stakeholder artifacts
- **`reports/figures/`** and **`reports/customer_recommendation_examples.md`**: visualizations and narrative examples to communicate results to non-technical stakeholders.

### Tests
- **`tests/test_ml.py`**: 10 tests covering the cleaning and feature-engineering modules, including a critical training-serving consistency test that verifies single-customer feature computation matches batch computation exactly.
- **`tests/test_api.py`**: 12 integration tests that boot the FastAPI app in-process and validate every endpoint's behavior, status codes, response shapes, and error handling.

### Current status
- Phase 1 modeling complete: notebooks 01–08 produce trained models and recommendation artifacts.
- Notebook logic refactored into reusable `src/ml/` modules with unit tests.
- FastAPI service implemented in `src/api/` with integration tests passing.
- All 22 tests passing.

### Notes
- `main.py` is currently a lightweight placeholder and can be extended into a production entrypoint.
- Ensure the raw data file is available at `data/raw/online_retail_II.csv` before running the notebooks.
- The notebooks remain available for exploration and for reproducing the analysis pipeline.
- The API expects trained models in `models/` and processed datasets in `data/processed/`. Run the notebooks once to generate these before starting the API for the first time.

## Roadmap

The project is being built out as a full production ML system. Current and upcoming phases:

- ✅ **Phase 1**: Notebooks for EDA, cleaning, features, segmentation, CLV, churn, market basket, and recommendation assembly.
- ✅ **Step 9**: Refactor notebook logic into reusable `src/ml/` package with tests.
- ✅ **Step 10**: FastAPI service exposing the models and recommendations over HTTP.
- ⏳ **Step 11**: Containerize the API with Docker for reproducible deployment.
- ⏳ **Step 12**: End-to-end integration tests against the running container.
- ⏳ **Step 13**: Deploy to AWS (ECS Fargate, ALB, DynamoDB for customer features and predictions, S3 for model artifacts) with authentication, structured logging, and secrets management.
- ⏳ **Step 14**: Scheduled retraining and prediction refresh via EventBridge + AWS Batch, with model versioning and drift monitoring.
- ⏳ **Step 15**: Streamlit dashboard for the marketing team to browse recommendations and segment composition.
- ⏳ **Step 16**: A/B testing infrastructure (DynamoDB for assignments, CloudWatch for outcomes) to measure the real business lift of the recommendations.