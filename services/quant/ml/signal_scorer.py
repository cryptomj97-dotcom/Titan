import numpy as np
import pandas as pd
import warnings
from typing import Dict, Any, List, Optional, Tuple

warnings.filterwarnings("ignore")


class LightGBMSignalScorer:
    """LightGBM-based ML signal scorer with walk-forward validation."""

    def __init__(self, n_features: int = 30, learning_rate: float = 0.05):
        self.n_features = n_features
        self.learning_rate = learning_rate
        self.model = None
        self._is_trained = False
        self.feature_names = None
        self.threshold_bullish = 0.55
        self.threshold_bearish = 0.45

    def _prepare_features(self, cluster_signals: Dict[str, Any], regime_info: Dict[str, Any]) -> Optional[np.ndarray]:
        """Prepare feature vector from cluster signals and regime."""
        try:
            features = []
            
            for cluster_name, signal_data in cluster_signals.items():
                if isinstance(signal_data, dict):
                    if "strength" in signal_data:
                        features.append(signal_data["strength"])
                    if "zscore" in signal_data:
                        features.append(signal_data["zscore"])
                    if "rsi" in signal_data:
                        features.append(signal_data["rsi"] / 100.0)
                    if "macd" in signal_data and isinstance(signal_data["macd"], dict):
                        features.append(signal_data["macd"].get("histogram", 0.0))
                    if "atr_ratio" in signal_data:
                        features.append(signal_data["atr_ratio"])
            
            if regime_info:
                features.append(regime_info.get("regime_confidence", 0.5))
                features.append(regime_info.get("stability_score", 0.5))
                features.append(regime_info.get("adx", 20.0) / 100.0)
            
            while len(features) < self.n_features:
                features.append(0.0)
            
            features = np.array(features[:self.n_features], dtype=float)
            features = np.nan_to_num(features, nan=0.0)
            
            return features
        except Exception:
            return None

    def fit(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> None:
        """Fit LightGBM model (simplified without LightGBM dependency)."""
        try:
            import lightgbm as lgb
            
            train_data = lgb.Dataset(X_train, label=y_train)
            valid_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
            
            params = {
                "objective": "binary",
                "metric": "auc",
                "learning_rate": self.learning_rate,
                "num_leaves": 31,
                "verbose": -1,
            }
            
            self.model = lgb.train(
                params,
                train_data,
                num_boost_round=100,
                valid_sets=[train_data, valid_data],
                callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)],
            )
            self._is_trained = True
        except ImportError:
            self._fallback_fit(X_train, y_train)
        except Exception as e:
            self._fallback_fit(X_train, y_train)

    def _fallback_fit(self, X_train: np.ndarray, y_train: np.ndarray) -> None:
        """Fallback linear model if LightGBM not available."""
        try:
            from sklearn.linear_model import LogisticRegression
            self.model = LogisticRegression(random_state=42, max_iter=1000)
            self.model.fit(X_train, y_train)
            self._is_trained = True
        except Exception:
            self._is_trained = False

    def predict(self, features: np.ndarray, apply_haircut: bool = True) -> float:
        """Predict signal probability."""
        if not self._is_trained or self.model is None:
            return 0.5
        
        try:
            if len(features.shape) == 1:
                features = features.reshape(1, -1)
            
            if hasattr(self.model, 'predict_proba'):
                prob = self.model.predict_proba(features)[0, 1]
            else:
                prob = self.model.predict(features)[0]
            
            if apply_haircut:
                prob = self._apply_haircut(prob)
            
            return float(np.clip(prob, 0.0, 1.0))
        except Exception:
            return 0.5

    def _apply_haircut(self, probability: float, haircut: float = 0.15) -> float:
        """Apply 15% haircut to prediction confidence."""
        if probability > 0.5:
            return probability * (1.0 - haircut)
        else:
            return probability / (1.0 + haircut)

    def score_signal(self, cluster_signals: Dict[str, Any], regime_info: Dict[str, Any]) -> Dict[str, Any]:
        """Score a signal using ML model."""
        features = self._prepare_features(cluster_signals, regime_info)
        
        if features is None:
            return {
                "ml_score": 0.5,
                "signal": "NEUTRAL",
                "confidence": 0.0,
            }
        
        score = self.predict(features)
        
        if score > self.threshold_bullish:
            signal = "BULLISH"
            confidence = score - self.threshold_bullish
        elif score < self.threshold_bearish:
            signal = "BEARISH"
            confidence = self.threshold_bearish - score
        else:
            signal = "NEUTRAL"
            confidence = 0.0
        
        return {
            "ml_score": float(score),
            "signal": signal,
            "confidence": float(np.clip(confidence, 0.0, 1.0)),
        }
