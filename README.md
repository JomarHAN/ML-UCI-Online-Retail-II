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

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
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

### Work with the notebooks

Start Jupyter Lab or Notebook and open the analysis pipeline:

```bash
jupyter lab
```

Then explore the notebooks in `notebooks/`:

- `01_EDA.ipynb` – exploratory data analysis
- `02_cleaning.ipynb` – data cleaning and validation
- `03_feature_engineering.ipynb` – customer-level feature building
- `04_segmentation.ipynb` – customer segmentation analysis
- `05_clv_prediction.ipynb` – CLV model development
- `06_churn_prediction.ipynb` – churn risk modeling
- `07_market_basket.ipynb` – market basket and product associations
- `08_recommendations.ipynb` – recommendation engine outputs

## Example Workflow

```bash
cd /Users/jomarnguyen/Desktop/uci-online-retail
source .venv/bin/activate
python -m pip install -e .
jupyter lab
```

Open the notebooks listed above and run the cells sequentially to reproduce the full data pipeline.

## Directory Structure

- `main.py` – package entrypoint
- `pyproject.toml` – project configuration and dependency definitions
- `data/raw/` – source dataset files
- `data/interim/` – intermediate processing outputs
- `data/processed/` – final datasets and recommendations
- `models/` – serialized model artifacts
- `notebooks/` – analysis, modeling, and recommendation notebooks
- `reports/` – generated analysis figures and summary outputs
- `src/` – placeholder package layout for future module code
- `tests/` – testing folder (currently empty)

## Data

The raw dataset is stored at `data/raw/online_retail_II.csv` and is expected to contain transaction-level retail sales and customer behavior data. Processed outputs include customer metadata and recommendations.

## Model Artifacts

- `models/churn_xgboost.joblib` – saved churn prediction model
- `models/clv_xgboost.joblib` – saved customer lifetime value model

## Extending the Project

To extend this repository, consider:

- converting notebook logic into reusable Python modules under `src/`
- adding end-to-end scripts for preprocessing, training, and inference
- implementing tests in `tests/`
- adding a CLI or API wrapper for model serving
- enriching recommendations with collaborative filtering or embeddings

## Notes

- The current `main.py` file is a lightweight placeholder and can be updated with a production entrypoint or CLI.
- Make sure the raw data file is present before rerunning the notebooks.


