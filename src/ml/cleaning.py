"""Data cleaning for the UCI Online Retail dataset.

Extracted form Notebook 02. The cleaning rules are expressed as small,
composable, individually-testable functions, then chained in `clean_transactions`.

Design note: every function takes a DataFrame and returns a new DataFrame
(no in-place mutation), so the pipeline is easy to reason about and test.
"""

from __future__ import annotations

import pandas as pd

from . import config

def load_raw(csv_path=None) -> pd.DataFrame:
    """Load the raw CSV with correct dtypes.
    Invoice and StockCode MUST be strings: cancellations look like 'C489449'
    and some stock codes are alphanumeric ('79323P'). Reading them as numbers
    silently loses information.
    """
    path = csv_path or config.RAW_CSV
    df = pd.read_csv(
        path,
        dtype={"Invoice": str, "StockCode": str, "CustomerID": str},
        parse_dates=["InvoiceDate"]
    )
    return df.rename(columns={"Customer ID": "CustomerID"})

def split_cancellations(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate cancellation rows (Invoice starts with 'C') from sales.
    Returns (sales, cancellations). Cancellations are kept separately so they
    can later become a return-rate feature, rather than being discarded.
    """
    is_cancel = df["Invoice"].str.startswith("C")
    return df[-is_cancel].copy(), df[is_cancel].copy()

def drop_non_product_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Remove admin/fee StockCodes (postage, bank charges, tests, etc.)."""
    out = df[-df["StockCode"].isin(config.NON_PRODUCT_CODES)].copy()
    out = out[-out["StockCode"].str.startswith("gift_", na=False)].copy()
    return out

def drop_non_positive(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with non-positive Quantity or Price (data errors / non-sales)."""
    return df[df["Quantity"] > 0 & df["Price"] > 0].copy()

def normalize_text(df: pd.DataFrame) -> pd.DataFrame:
    """Strip + uppercase Description, strip Country."""
    out = df.copy()
    out['Description'] = out["Description"].str.strip().str.upper()
    out['Country'] = out['Country'].str.strip()
    return out

def drop_admin_description(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows whose Description is a warehouse annotation, not a product.
    Must run AFTER normalize_text since the admin set is uppercase."""
    return df[-df['Description'].isin(config.ADMIN_DESCRIPTIONS)].copy()

def canonicalize_descriptions(df: pd.DataFrame) -> pd.DataFrame:
    """Give each StockCode a single canonical Description (its nost common one)."""
    out = df.copy()
    canonical = (
        out.dropna(subset=["Description"])
        .groupby("StockCode")["Description"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
    )
    out["Description"] = out["Description"].map(canonical)
    return out.dropna(subset=["Description"]).copy()

def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add Revenue and calendar-part columns used downstream."""
    out = df.copy()
    out["Revenue"] = out["Quantity"] * out["Price"]
    out["is_bulk_order"] = out["Quantity"] >= config.BULK_ORDER_QUANTITY_THRESHOLD
    out["Year"] = out["InvoiceDate"].dt.year.astype("int16")
    out["Month"] = out["InvoiceDate"].dt.month.astype("int8")
    out["DayOfWeek"] = out["InvoiceDate"].dt.day_name()
    out["Hour"] = out["InvoiceDate"].dt.hour.astype("int8")
    out["Date"] = out["InvoiceDate"].dt.date
    return out

def clean_transactions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Full cleaning pipeline. Returns (clean_sales, cancellations).
    Mirrors Notebook 02 exactly, but as one importable function."""
    sales, cancellations = split_cancellations(df)
    sales = drop_non_product_codes(sales)
    sales = drop_non_positive(sales)
    sales = normalize_text(sales)
    sales = drop_admin_description(sales)
    sales = canonicalize_descriptions(sales)
    sales = add_derived_columns(sales)
    return sales, cancellations

def to_customer_level(clean_sales: pd.DataFrame) -> pd.DataFrame:
    """Filter to rows with a valid CustomerID (for customer modeling)."""
    return clean_sales.dropna(subset=["CustomerID"]).copy()