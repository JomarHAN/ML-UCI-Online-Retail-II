"""Model loading and inference wrappers.
Extracted from Notebook 05 (CLV) and 06 (churn). Each predictor loads its
joblib artifact one and exposes a clean `predict` method. The artifacts store
the feature_names list, so we can align incoming feature frames to the exact
column order the model was trained on - another anti-skew safeguard.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from . import config

def _prepare_feature_matrix(features: pd.DataFrame, features_names: list[str]) -> pd.DataFrame:
    """One-hot encode segment and align to the model's trained feature order.
    Any expected column missing from the input is added as zeros (e.g. a segment
    that does not appear in a single-customer serving request). Extra columns are
    dropped. Final column order matches feature_name exactly.
    """
    encoded = pd.get_dummies(features, columns=['segment'], prefix='segment') if 'segment' in features.columns else features.copy()
    
    for col in features_names:
        if col not in encoded.columns:
            encoded[col] = 0
    return encoded[features_names]

class CLVPredictor:
    """Predict 90-day customer revenue. Model was trained on log1p(target)"""
    
    def __init__(self, model_path=None):
        artifact = joblib.load(model_path or config.CLV_MODEL_FILE)
        self.model = artifact['model']
        self.feature_names = artifact['feature_names']
        self.metrics = artifact.get('metrics', {})
        
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        X = _prepare_feature_matrix(features, self.feature_names)
        log_pred = self.model.predict(X)
        # Invert the log1p transform and clip negative to zero
        return np.clip(np.expm1(log_pred), 0, None)
    
class ChurnPredictor:
    """Predicts probability a customer is ACTIVE (will purchase) in next 90d.
    churn_risk = 1 - p_active. The model's positive class (1) is 'active'
    so predict_proba[:,1] is p_active
    """
    
    def __init__(self, model_path=None):
        artifact = joblib.load(model_path or config.CHURN_MODEL_FILE)
        self.model = artifact['model']
        self.feature_names = artifact['feature_names']
        self.threshold = artifact.get('chosen_threshold', 0.5)
        self.metrics = artifact.get('metrics', {})
        
    def predict_active_proba(self, features: pd.DataFrame) -> np.ndarray:
        X = _prepare_feature_matrix(features, self.feature_names)
        return self.model.predict_proba(X)[:,1]
    
    def predict_churn_risk(self, features: pd.DataFrame) -> np.ndarray:
        return 1.0 - self.predict_active_proba(features)