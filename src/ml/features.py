"""Customer-level feature engineering.
Extracted from Notebook 03. THE most important module for avoiding
training-serving skew: `build_customer_features` is the single function used 
both to build the training set AND to compute features for a live customer at 
inference time. If training and serving ever diverge, this is where bugs hide,
so there is exactly one implementation.

The function takes customer-level transactions plus a snapshot date and returns
one feature row per customer. It does NOT compute targets - targers require
future data and are only available during training (see `add_targets`).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from . import config

def build_customer_features(
    transactions: pd.DataFrame,
    snapshot_date: datetime,
    cancellations: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Build one feature row per customer using ONLY data up snapshot_date.
    
    Parameters:
    -----------
    transactions: customer-level clean sales (must have CustomerID, InvoiceDate, Invoice, StockCode, Quantity, Price, Revenue, Country)
    snapshot_date: the 'as of' date. Features use only rows on or before this.
    cancellations: optional cancellations table for return-rate features.
    
    Returns
    --------
    DataFrame woth one row per customer and -35 feature columns. No regrets.
    """
    # Guard: only use data up to the snapshot (no future leakage)
    feat_df = transactions[transactions["InvoiceDate"] <= snapshot_date].copy()
    if feat_df.empty:
        return pd.DataFrame()
    
    features = (
        pd.DataFrame({'CustomerID': feat_df['CustomerID'].unique()})
        .sort_values('CustomerID')
        .reset_index(drop=True)
    )
    
    features = _add_rfm(features, feat_df, snapshot_date)
    features = _add_behavioral(features, feat_df)
    features = _add_product_mix(features, feat_df)
    features = _add_trend(features, feat_df, snapshot_date)
    features = _add_geography(features, feat_df)
    features = _add_returns(features, cancellations, snapshot_date)
    features = _finalize_missing(features)
    return features

def _add_rfm(features, feat_df, snapshot_date):
    rfm = feat_df.groupby('CustomerID').agg(
        last_purchase_date=("InvoiceDate", "max"),
        first_purchase_date=("InvoiceDate", "min"),
        frequency=("Invoice", "nunique"),
        monetary=("Revenue", "sum"),
        total_units=("Quantity", "sum"),
        total_line_items=("Invoice", "count")
    ).reset_index()
    rfm["recency_days"] = (snapshot_date - rfm["last_purchase_date"]).dt.days
    rfm["tenure_days"] = (rfm["last_purchase_date"] - rfm["first_purchase_date"]).dt.days
    rfm["customer_age_days"] = (snapshot_date - rfm["first_purchase_date"]).dt.days
    return features.merge(
        rfm.drop(columns=["last_purchase_date", "first_purchase_date"]),
        on="CustomerID", how="left"
    )
    
def _add_behavioral(features, feat_df):
    orders = feat_df.groupby(['CustomerID', 'Invoice']).agg(
        order_value=("Revenue","sum"),
        order_units=("Quantity","sum"),
        order_distinct_products=("StockCode", "nunique"),
        order_date=("InvoiceDate", "min")
    ).reset_index()
    
    behavioral = orders.groupby("CustomerID").agg(
        avg_order_value=("order_value", "mean"),
        median_order_value=("order_value", "median"),
        std_order_value=("order_value","std"),
        max_order_value=("order_value", "max"),
        avg_basket_size=("order_units","mean"),
        avg_distinct_products_per_order=("order_distinct_products", "mean")
    ).reset_index()
    features = features.merge(behavioral, on='CustomerID', how='left')
    
    orders_sorted = orders.sort_values(["CustomerID","order_date"])
    orders_sorted["days_since_prev"] = (
        orders_sorted.groupby("CustomerID")["order_date"].diff().dt.days
    )
    cadence = orders_sorted.groupby("CustomerID")["days_since_prev"].agg(
        avg_days_between_orders="mean",
        std_days_between_orders="std",
        max_days_between_orders="max"
    ).reset_index()
    return features.merge(cadence, on="CustomerID", how="left")

def _add_product_mix(features, feat_df):
    mix = feat_df.groupby("CustomerID").agg(
        unique_products=("StockCode","nunique"),
    ).reset_index()
    features = features.merge(mix, on="CustomerID", how="left")
    features["product_diversity"] = (
        features["unique_products"] / features["total_line_items"].clip(lower=1)
    )
    return features

def _add_trend(features, feat_df, snapshot_date):
    windows = {
        "last_30d": feat_df[feat_df["InvoiceDate"] > snapshot_date - timedelta(days=30)],
        "last_60d": feat_df[feat_df["InvoiceDate"] > snapshot_date - timedelta(days=60)],
        "last_90d": feat_df[feat_df["InvoiceDate"] > snapshot_date - timedelta(days=90)],
        "prior_30d": feat_df[
            (feat_df["InvoiceDate"] > snapshot_date - timedelta(days=60))
            & (feat_df["InvoiceDate"] <= snapshot_date - timedelta(days=30))
        ]
    }
    for name, window in windows.items():
        agg = window.groupby("CustomerID").agg(
            **{f'revenue_{name}':('Revenue','sum'),
               f'orders_{name}':('Invoice','nunique')}
        ).reset_index()
        features = features.merge(agg, on='CustomerID', how='left')
        
    trend_cols = [c for c in features.columns
                  if c.starswith(('revenue_last','orders_last','revenue_prior','orders_prior'))]
    features[trend_cols] = features[trend_cols].fillna(0)
    
    features['revenue_trend_ratio'] = (
        features['revenue_last_30d'] / (features['revenue_prior_30d'] + config.RATIO_EPSILON)
    )
    
    feat_df = feat_df.copy()
    feat_df['YearMonth'] = feat_df['InvoiceDate'].dt.to_period('M')
    months = feat_df.groupby('CustomerID')['YearMonth'].nunique().reset_index(name='month_active')
    return features.merge(months, on='CustomerID', how='left')

def _add_geography(features, feat_df):
    primary = (
        feat_df.groupby('CustomerID')['Country']
        .agg(lambda x: x.mode().iloc[0])
        .reset_index(name='primary_country')
    )
    features = features.merge(primary, on='CustomerID', how='left')
    features['is_uk'] = (features['primary_country'] == 'United Kingdom').astype(int)
    return features

def _add_returns(features, cancellations, snapshot_date):
    if cancellations is None or cancellations.empty:
        features['return_count'] = 0
        features['return_value'] = 0.0
        features['return_rate'] = 0.0
        return features
    
    cancel = cancellations[
        (cancellations['InvoiceDate'] <= snapshot_date)
        & cancellations['CustomerID'].notna()
    ].copy()
    cancel['return_value'] = cancel['Quantity'].abs() * cancel['Price'].abs()
    returns = cancel.groupby('CustomerID').agg(
        return_count=('Invoice','nunique'),
        return_value=('return_value','sum')
    ).reset_index()
    features = features.merge(returns, on='CustomerID', how='left')
    features['return_count'] = features['return_count'].fillna(0).astype(int)
    features['return_value'] = features['return_value'].fillna(0)
    features['return_rate'] = (
        features['return_value'] / features['monetary'] + config.RATIO_EPSILON
    )
    return features

def _finalize_missing(features):
    """Fill NaNs intentionally and add the one-time-customer flag.
    Identical logic to Notebook 03 Section 10 so serving matches training.
    """
    features['is_one_time_customer'] = (features['frequency'] == 1).astype(int)
    features['avg_days_between_orders'] = features['avg_days_between_orders'].fillna(
        features['recency_days']
    )
    features['std_days_between_orders'] = features['std_days_between_orders'].fillna(0)
    features['max_days_between_orders'] = features['max_days_between_orders'].fillna(
        features['recency_days']
    )
    features['std_order_value'] = features['std_order_value'].fillna(0)
    return features

def add_targets(
    features: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot_date: datetime
) -> pd.DataFrame:
    """Add training targets from the window AFTER snapshot_date
    Only used during training - at serving time the future us unknown.
    """
    target_df = transactions[transactions['InvoiceDate'] > snapshot_date]
    targets = target_df.groupby('CustomerID').agg(
        target_revenue_90d=('Revenue','sum'),
        target_orders_90d=('Invoice','nunique')
    ).reset_index()
    out = features.merge(targets, on='CustomerID', how='left')
    out['target_revenue_90d'] = out['target_revenue_90d'].fillna(0)
    out['target_orders_90d'] = out['target_orders_90d'].fillna(0).astype(int)
    out['target_purchased_90d'] = (out['target_orders_90d'] > 0).astype(int)
    return out

def default_snapshot_date(transactions: pd.DataFrame) -> datetime:
    """Snapshot = max date minus the target window. Matches Notebook 03."""
    return transactions['InvoiceDate'].max() - timedelta(days=config.TARGET_WINDOW_DAYS)