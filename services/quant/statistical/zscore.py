import numpy as np
import pandas as pd
from typing import Dict, Any


class ZScoreModel:
    """Z-score based price deviation detector."""

    def __init__(self, period: int = 20, threshold: float = 2.0):
        self.period = period
        self.threshold = threshold

    def _calculate_zscore(self, prices: np.ndarray) -> np.ndarray:
        """Calculate z-score for price deviations."""
        if len(prices) < self.period:
            return np.zeros_like(prices)
        
        sma = pd.Series(prices).rolling(self.period).mean()
        std = pd.Series(prices).rolling(self.period).std()
        
        zscore = (prices - sma) / std.replace(0, 1e-10)
        return zscore.fillna(0).values

    def _calculate_rolling_percentile(self, prices: np.ndarray) -> np.ndarray:
        """Calculate how extreme current price is vs range."""
        if len(prices) < self.period:
            return np.full_like(prices, 50.0)
        
        rolling_min = pd.Series(prices).rolling(self.period).min()
        rolling_max = pd.Series(prices).rolling(self.period).max()
        
        percentile = 100 * (prices - rolling_min) / (rolling_max - rolling_min).replace(0, 1e-10)
        return percentile.fillna(50).values

    def detect(self, ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Detect price extremes using z-score."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        
        if len(closes) < self.period:
            return {
                "signal": "NEUTRAL",
                "strength": 0.0,
                "zscore": 0.0,
                "percentile": 50.0,
            }
        
        zscores = self._calculate_zscore(closes)
        current_zscore = zscores[-1]
        
        percentiles = self._calculate_rolling_percentile(closes)
        current_percentile = percentiles[-1]
        
        if current_zscore > self.threshold:
            signal = "BEARISH"
            strength = min(1.0, current_zscore / (self.threshold * 2))
        elif current_zscore < -self.threshold:
            signal = "BULLISH"
            strength = min(1.0, abs(current_zscore) / (self.threshold * 2))
        else:
            signal = "NEUTRAL"
            strength = 0.5
        
        return {
            "signal": signal,
            "strength": float(strength),
            "zscore": float(current_zscore),
            "percentile": float(current_percentile),
        }
