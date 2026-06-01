import numpy as np
import pandas as pd
import warnings
from typing import Dict, Any, List, Optional

warnings.filterwarnings("ignore")


class AnomalyDetector:
    """Isolation Forest-based anomaly detector for signal validation."""

    def __init__(self, contamination: float = 0.1, lookback: int = 252):
        self.contamination = contamination
        self.lookback = lookback
        self.model = None
        self._is_trained = False

    def _prepare_features(self, ohlcv: Dict[str, list], lookback: int = 20) -> np.ndarray:
        """Prepare features for anomaly detection."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        volumes = np.array([c.get("volume", 1) for c in ohlcv["1D"]], dtype=float)
        
        returns = np.log(closes[1:] / closes[:-1]) if len(closes) > 1 else np.array([0.0])
        rolling_vol = pd.Series(returns).rolling(lookback).std().fillna(0.0).values
        
        rolling_avg_vol = pd.Series(volumes).rolling(lookback).mean().fillna(1.0).values
        vol_ratio = volumes / rolling_avg_vol.replace(0, 1)
        vol_ratio = np.clip(vol_ratio, 0.1, 10.0)
        
        price_range = np.array([c["high"] - c["low"] for c in ohlcv["1D"]])
        rolling_range = pd.Series(price_range).rolling(lookback).mean().fillna(1.0).values
        range_ratio = price_range / rolling_range.replace(0, 1)
        range_ratio = np.clip(range_ratio, 0.1, 10.0)
        
        skew = pd.Series(returns).rolling(lookback).skew().fillna(0.0).values
        kurt = pd.Series(returns).rolling(lookback).apply(lambda x: pd.Series(x).kurtosis()).fillna(0.0).values
        
        features = np.column_stack([
            returns,
            rolling_vol,
            vol_ratio,
            range_ratio,
            skew,
            kurt,
        ])
        
        features = np.nan_to_num(features, nan=0.0)
        features = np.clip(features, -10, 10)
        
        return features

    def fit(self, historical_ohlcv: List[Dict[str, list]]) -> None:
        """Train anomaly detector on historical data."""
        try:
            all_features = []
            for ohlcv in historical_ohlcv:
                features = self._prepare_features(ohlcv)
                if len(features) > 0:
                    all_features.append(features)
            
            if not all_features:
                self._is_trained = False
                return
            
            X_train = np.vstack(all_features)
            
            try:
                from sklearn.ensemble import IsolationForest
                self.model = IsolationForest(
                    contamination=self.contamination,
                    random_state=42,
                    n_estimators=100,
                )
                self.model.fit(X_train)
                self._is_trained = True
            except ImportError:
                self._fallback_fit(X_train)
        except Exception:
            self._is_trained = False

    def _fallback_fit(self, X_train: np.ndarray) -> None:
        """Fallback anomaly detector using statistical methods."""
        self.mean = np.mean(X_train, axis=0)
        self.std = np.std(X_train, axis=0) + 1e-10
        self._is_trained = True

    def predict(self, ohlcv: Dict[str, list], apply_haircut: bool = True) -> Dict[str, Any]:
        """Detect anomalies in current market data."""
        if not self._is_trained:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "severity": "NORMAL",
            }
        
        features = self._prepare_features(ohlcv)
        
        if len(features) == 0:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "severity": "NORMAL",
            }
        
        try:
            if self.model is not None:
                if hasattr(self.model, 'decision_function'):
                    anomaly_scores = self.model.decision_function(features)
                    predictions = self.model.predict(features)
                    anomaly_score = float(-np.mean(anomaly_scores))
                else:
                    normalized = (features - self.mean) / self.std
                    anomaly_score = float(np.mean(np.abs(normalized)))
                    predictions = np.where(np.max(np.abs(normalized), axis=1) > 3, -1, 1)
            
            is_anomaly = predictions[-1] == -1
            
            if apply_haircut:
                anomaly_score = anomaly_score * 0.85
            
            if anomaly_score > 0.7:
                severity = "CRITICAL"
            elif anomaly_score > 0.5:
                severity = "HIGH"
            elif anomaly_score > 0.3:
                severity = "MEDIUM"
            else:
                severity = "LOW"
            
            return {
                "is_anomaly": bool(is_anomaly),
                "anomaly_score": float(np.clip(anomaly_score, 0.0, 1.0)),
                "severity": severity,
            }
        except Exception:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "severity": "NORMAL",
            }

    def validate_signal(self, cluster_signals: Dict[str, Any], ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Validate signal against anomalies."""
        anomaly_result = self.predict(ohlcv)
        
        is_valid = not anomaly_result["is_anomaly"]
        confidence_reduction = anomaly_result["anomaly_score"] * 0.3
        
        return {
            "is_valid": is_valid,
            "anomaly_score": anomaly_result["anomaly_score"],
            "severity": anomaly_result["severity"],
            "confidence_reduction": float(confidence_reduction),
        }

    def get_market_health(self, ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Overall market health assessment."""
        anomaly_result = self.predict(ohlcv, apply_haircut=False)
        
        if anomaly_result["anomaly_score"] > 0.6:
            health = "STRESSED"
        elif anomaly_result["anomaly_score"] > 0.4:
            health = "VOLATILE"
        else:
            health = "NORMAL"
        
        return {
            "health_status": health,
            "anomaly_level": anomaly_result["anomaly_score"],
            "is_anomalous": anomaly_result["is_anomaly"],
        }
