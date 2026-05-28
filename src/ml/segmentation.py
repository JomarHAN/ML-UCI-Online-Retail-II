"""RFM scoring and segment assignment.
Extracted from Notebook 04. Pure functions, no plotting. The K-Means part of
Notebook 04 is ommited here because the named RFM segments are what downstream
code (models, recommender) actually consumes.
"""
from __future__ import annotations

import pandas as pd

def add_rfm_scores(features: pd.DataFrame) -> pd.DataFrame:
    """Add R/F/M quintile scores (1-5) and a combined RFM_score string.
    Uses .rank(method='first') on all three dimensions to handle the many
    tied values (e.g. frequency==1) cleanly - consistent treatment as fixed
    in the Notebook 04 review.
    """
    out = features.copy()
    out['R_score'] = pd.qcut(
        out['recency_days'].rank(method='first'), 5, labels=[5, 4, 3, 2, 1]
    ).astype(int)
    out['F_score'] = pd.qcut(
        out['frequency'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5]
    ).astype(int)
    out['M_score'] = pd.qcut(
        out['monetary'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5]
    ).astype(int)
    out['RFM_score'] = (
        out['R_score'].astype(str) + out['F_score'].astype(str) + out['M_score'].astype(str)
    )
    return out

def _assign_segment(row) -> str:
    r, f, m = row['R_score'], row['F_score'], row['M_score']
    if r >= 4 and f >= 4 and m >= 4:
        return 'Champions'
    if r <= 2 and f >= 4 and m >= 4:
        return "Cannot Lose Them"
    if r >= 3 and f >= 3 and m >= 3:
        return 'Loyal Customers'
    if r >= 4 and f <= 2:
        return 'New Customers' if f == 1 else 'Potential Loyalists'
    if r <= 3 and f >= 3 and m >= 3:
        return "At Risk"
    if r <= 2 and f <= 2 and m <= 2:
        return 'Hibernating' if r == 2 else 'Lost'
    return "Need Attention"

def assign_segments(features: pd.DataFrame) -> pd.DataFrame:
    """Add the named `segment` column based on RFM scores."""
    out = features.copy()
    if 'R_score' not in out.columns:
        out = add_rfm_scores(out)
    out['segment'] = out.apply(_assign_segment, axis=1)
    return out