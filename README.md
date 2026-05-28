# UCI Online Retail Analytics

A data science project for customer analytics and recommendations using the UCI Online Retail dataset. The repository includes raw and processed data, exploratory notebooks, machine learning artifacts, and a lightweight package entrypoint.

## Overview

This project analyzes retail transaction data to build customer-level insights, including:

- customer lifetime value (CLV) prediction
- churn risk modeling
- customer segmentation and feature engineering
- product recommendation generation

The workflow is notebook-driven with reusable artifacts saved in `models/` and processed datasets in `data/processed/`.

## Technical Architecture

The repository follows a modular analysis pipeline:

1. **Data ingestion**
   - Raw data is stored in `data/raw/online_retail_II.csv`
   - Interim and processed datasets are stored under `data/interim/` and `data/processed/`

2. **Exploration and cleaning**
   - Jupyter notebooks explore dataset quality, describe customer behavior, and perform cleansing.

3. **Feature engineering**
   - Customer features are derived from transactional history, frequency, recency, monetary value, and purchase behavior.

4. **Modeling**
   - XGBoost models are trained for churn and CLV prediction.
   - Saved model artifacts are stored in `models/churn_xgboost.joblib` and `models/clv_xgboost.joblib`.

5. **Recommendation generation**
   - Product recommendations and metadata are stored in `data/processed/recommendations.jsonl` and `data/processed/customer_features_metadata.json`.

6. **Presentation and outputs**
   - Notebooks produce figures, tables, and example outputs collected in `reports/figures/`.

## Installation

### Requirements

- Python 3.11 or newer
- `pip`

### Install dependencies

From the repository root, create a named virtual environment for this project:

```bash
python -m venv .venv
```

If you prefer a distinct name, replace `.venv` with your chosen environment name:

```bash
python -m venv myenv
```

Activate the environment:

```bash
source .venv/bin/activate
```

or for a custom name:

```bash
source myenv/bin/activate
```

Then upgrade `pip` and install the project:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

### Install development dependencies

```bash
python -m pip install -e .[dev]
```

## Usage

### Run the package

The current package entrypoint is a placeholder:

```bash
python main.py
```

This prints a simple message from the package. The primary project work is contained in the notebooks.
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
- **`models/churn_xgboost.joblib`** and **`models/clv_xgboost.joblib`**: serialized model artifacts produced from the notebooks. Joblib was selected for fast load/save in Python. Business meaning: these artifacts power operational predictions (churn prioritization, CLV-driven budgeting).

### Notebooks (detailed)
Each notebook contains a self-contained stage of the analysis pipeline. Below is a concise mapping of the typical actions you performed and why, plus the business interpretation.

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
   - What: clustering or rule-based segmentation (KMeans, deciles), profiling segments.
   - Why: group customers with similar lifetime value and behavior.
   - Business meaning: drives targeted marketing, merchandising, and retention strategies.

- **`notebooks/05_clv_prediction.ipynb`** — CLV Modeling
   - What: train/validate XGBoost model for Customer Lifetime Value, save `clv_xgboost.joblib`.
   - Why: estimate future monetary value to inform acquisition and retention ROI.
   - Business meaning: informs budget allocation and customer prioritization.

- **`notebooks/06_churn_prediction.ipynb`** — Churn Risk Modeling
   - What: define churn label, train XGBoost churn model, evaluate and export predictions.
   - Why: identify at-risk customers for targeted interventions.
   - Business meaning: reduces churn-driven revenue loss through prioritized retention campaigns.

- **`notebooks/07_market_basket.ipynb`** — Market-Basket Analysis
   - What: itemset mining, association rules, co-occurrence analysis.
   - Why: discover product affinities for cross-sell and bundling.
   - Business meaning: increases average order value and improves promotion effectiveness.

- **`notebooks/08_recommendations.ipynb`** — Recommendation Assembly
   - What: score and rank candidate products per customer, apply business rules, export `recommendations.jsonl`.
   - Why: produce personalized recommendations ready for ingestion by marketing or product systems.
   - Business meaning: directly impacts conversions and personalization-driven revenue uplift.

### Source package and code layout
- **`src/`** (data, features, models, recommendations): placeholder package structure for converting notebook logic to reusable modules. Moving code here enables productionization, testing, and reuse.

### Reports and stakeholder artifacts
- **`reports/figures/`** and **`reports/customer_recommendation_examples.md`**: visualizations and narrative examples to communicate results to non-technical stakeholders.

### Tests
- **`tests/`**: contains unit and integration tests for notebook transforms, data processing, and model scoring. The current suite includes 10 passing tests.

### Current status
- Notebook functions have been converted into reusable modules under `src/`.
- Unit tests are implemented and passing.
- Build/package assets and model artifacts are ready for reuse.

### Notes
- `main.py` is currently a lightweight placeholder and can be extended into a production entrypoint.
- Ensure the raw data file is available before running the notebooks.
- The notebooks remain available for exploration and for reproducing the analysis pipeline.


## Next steps

The project is actively progressing. Current work includes refining the reusable `src/` modules, expanding unit and integration coverage, and turning notebook analysis into a fully reproducible pipeline.
