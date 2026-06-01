import numpy as np
import pandas as pd
from typing import Dict, Any


class AutocorrelationModel:
    """Autocorrelation-based mean reversion detector."""

    def __init__(self, lags: int = 20, threshold: float = 0.1):
        self.lags = lags
        self.threshold = threshold

    def _calculate_acf(self, returns: np.ndarray, nlags: int) -> np.ndarray:
        """Calculate autocorrelation function."""
        if len(returns) < nlags + 1:
            return np.zeros(nlags + 1)
        
        c0 = np.sum((returns - np.mean(returns)) ** 2) / len(returns)
        acf_values = [1.0]
        
        for k in range(1, nlags + 1):
            ck = np.sum((returns[:-k] - np.mean(returns)) * (returns[k:] - np.mean(returns))) / len(returns)
            acf_values.append(ck / c0)
        
        return np.array(acf_values)

    def _mean_reversion_strength(self, acf_values: np.ndarray) -> float:
        """Calculate mean reversion strength from ACF."""
        significant_acf = acf_values[1:6] if len(acf_values) > 5 else acf_values[1:]
        
        if len(significant_acf) == 0:
            return 0.0
        
        if np.sum(significant_acf < 0) > len(significant_acf) / 2:
            return 1.0
        elif np.sum(significant_acf > 0) > len(significant_acf) / 2:
            return -1.0
        else:
            return 0.0

    def _hurst_via_acf(self, acf_values: np.ndarray) -> float:
        """Estimate Hurst exponent via ACF."""
        if len(acf_values) < 3:
            return 0.5
        
        significant_acf = acf_values[1:11] if len(acf_values) > 10 else acf_values[1:]
        sum_acf = np.sum(significant_acf)
        
        if sum_acf > 0.2:
            return min(1.0, 0.5 + sum_acf / 2)
        elif sum_acf < -0.2:
            return max(0.0, 0.5 + sum_acf / 2)
        else:
            return 0.5

    def detect(self, ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Detect mean reversion via autocorrelation."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        
        if len(closes) < self.lags + 10:
            return {
                "signal": "NEUTRAL",
                "strength": 0.0,
                "acf_sum": 0.0,
                "mean_reversion_score": 0.0,
            }
        
        returns = np.log(closes[1:] / closes[:-1])
        acf_values = self._calculate_acf(returns, self.lags)
        
        mean_rev_strength = self._mean_reversion_strength(acf_values)
        acf_sum = np.sum(acf_values[1:6]) if len(acf_values) > 5 else 0.0
        hurst_est = self._hurst_via_acf(acf_values)
        
        if mean_rev_strength > self.threshold:
            signal = "BULLISH"
            strength = min(1.0, mean_rev_strength)
        elif mean_rev_strength < -self.threshold:
            signal = "BEARISH"
            strength = min(1.0, abs(mean_rev_strength))
        else:
            signal = "NEUTRAL"
            strength = 0.5
        
        return {
            "signal": signal,
            "strength": float(strength),
            "acf_sum": float(acf_sum),
            "mean_reversion_score": float(mean_rev_strength),
            "hurst_estimate": float(hurst_est),
        }
