"""Tests for the ML package.
The most important test here is `test_training_serving_consistency`: it proves
the computing features for a single customer in isolation produces the SAME values
as computing them for the whole barch. This is the guarantee that prevents training-serving skew
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make `src` importable when running pytest from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ml import cleaning, features, config

@pytest.fixture(scope='module')
def raw():
    return cleaning.load_raw()

@pytest.fixture(scope='module')
def clean_data(raw):
    sales, cancellations = cleaning.clean_transactions(raw)
    customer_level = cleaning.to_customer_level(sales)
    return customer_level, cancellations

# -----------------------------------
# Cleaning tests
# -----------------------------------
def test_cleaning_removes_cancellations(raw):
    sales, cancellations = cleaning.clean_transactions(raw)
    # No invoice in clean sales should start with 'C'
    assert not sales['Invoice'].str.startswith('C').any()
    # Cancellations should all start with 'C'
    assert cancellations['Invoice'].str.startswith('C').all()
   
    
def test_cleaning_no_negative_values(clean_data):
    customer_level, _ = clean_data
    assert (customer_level['Quantity'] > 0).all()
    assert (customer_level['Price'] > 0).all()
   

def test_cleaning_no_null_descriptions(clean_data):
    customer_level, _ = clean_data
    assert customer_level['Description'].notna().all()
    
    
def test_cleaning_no_admin_codes(clean_data):
    customer_level, _ = clean_data
    assert not customer_level['StockCode'].isin(config.NON_PRODUCT_CODES).any()
    
    
def test_cleaning_revenue_column(clean_data):
    customer_level, _ = clean_data
    expected = customer_level['Quantity'] * customer_level['Price']
    assert (customer_level['Revenue'] - expected).abs().max() < 1e-6
    
    
# -----------------------------------
# Feature engineering tests
# -----------------------------------
def test_features_one_row_per_customer(clean_data):
    customer_level, cancellations = clean_data
    snapshot = features.default_snapshot_date(customer_level)
    feats = features.build_customer_features(customer_level, snapshot, cancellations)
    assert feats['CustomerID'].nunique() == len(feats)
    
    
def test_features_no_future_leakage(clean_data):
    """Features must use only data up to snapshot. We verify by checking that
    recency_days is always >= 0 (last purchase is on or before snapshot)."""
    customer_level, cancellations = clean_data
    snapshot = features.default_snapshot_date(customer_level)
    feats = features.build_customer_features(customer_level, snapshot, cancellations)
    assert (feats['recency_days'] >= 0).all()
    
    
def test_features_no_nans_in_key_column(clean_data):
    customer_level, cancellations = clean_data
    snapshot = features.default_snapshot_date(customer_level)
    feats = features.build_customer_features(customer_level, snapshot, cancellations)
    key_cols = ['recency_days', 'frequency', 'monetary', 'avg_order_value',
                'avg_days_between_orders', 'is_one_time_customer']
    for col in key_cols:
        assert feats[col].notna().all(), f'NaN found in {col}'
        

def test_recency_correlates_negatively_with_repurchase(clean_data):
    """Sanity check from Notebook 03: recent buyers repurchase more."""
    customer_level, cancellations = clean_data
    snapshot = features.default_snapshot_date(customer_level)
    feats = features.build_customer_features(customer_level, snapshot, cancellations)
    feats = features.add_targets(feats, customer_level, snapshot)
    corr = feats['recency_days'].corr(feats['target_purchased_90d'])
    assert corr < 0, f'Expected negative correlation, got {corr}'
    
    
# -----------------------------------
# THE critical test: training-serving consistency
# -----------------------------------
def test_training_serving_consistency(clean_data):
    """Computing features for a single customer in isolation must match the 
    values computed in the full batch. This is the anti-skew guarantee.
    We pick a few representative customers, compute their features both ways,
    and assert the feature rows are identical.
    """
    customer_level, cancellations = clean_data
    snapshot = features.default_snapshot_date(customer_level)
    
    # Batch: compute all features at once
    batch = features.build_customer_features(customer_level, snapshot, cancellations)
    
    # Pick 5 customers spanning the activity range
    sample_ids = (
        batch.sort_values('monetary')
        .iloc[[0, len(batch) // 4, len(batch) // 2, 3 * len(batch) // 4, -1]]
        ['CustomerID'].tolist()
    )
    
    numeric_cols = batch.select_dtypes(include='number').columns
    
    for cid in sample_ids:
        # Serving: compute features for just this customer's transactions
        cust_txns = customer_level[customer_level['CustomerID'] == cid]
        cust_cancels = cancellations[cancellations['CustomerID'] == cid]
        single = features.build_customer_features(cust_txns, snapshot, cust_cancels)
        
        batch_row = batch[batch['CustomerID'] == cid][numeric_cols].reset_index(drop=True)
        single_row = single[single['CustomerID'] == cid][numeric_cols].reset_index(drop=True)
        
        # Compare numeric features (allow tiny float tolerance)
        pd.testing.assert_frame_equal(
            batch_row, single_row, check_dtype=False, atol=1e-6,
            obj=f'customer {cid}'
        )