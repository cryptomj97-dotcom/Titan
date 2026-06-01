import numpy as np
import warnings
from typing import Dict, Any

warnings.filterwarnings("ignore")


class FractalModel:
    """Higuchi fractal dimension for market complexity detection."""

    def __init__(self):
        self.max_k = 32
        self.complexity_threshold_low = 1.3
        self.complexity_threshold_high = 1.6

    def _higuchi_fractal_dimension(self, prices: np.ndarray) -> float:
        """Calculate Higuchi fractal dimension."""
        if len(prices) < 100:
            return 1.5
        
        lnks = []
        lnf = []
        
        for k in range(1, min(self.max_k, len(prices) // 10)):
            lk = []
            for m in range(k):
                indices = np.arange(m, len(prices), k)
                if len(indices) < 2:
                    continue
                prices_subset = prices[indices]
                lm = np.sum(np.abs(np.diff(prices_subset))) * (len(prices) - 1) / ((len(prices) // k) ** 2 * k)
                lk.append(lm)
            
            if len(lk) > 0:
                avg_lk = np.mean(lk)
                if avg_lk > 0:
                    lnks.append(np.log(k))
                    lnf.append(np.log(avg_lk))
        
        if len(lnks) < 2:
            return 1.5
        
        lnks = np.array(lnks)
        lnf = np.array(lnf)
        
        coeffs = np.polyfit(lnks, lnf, 1)
        fd = -coeffs[0]
        
        return float(np.clip(fd, 1.0, 2.0))

    def _volatility_clustering(self, returns: np.ndarray) -> float:
        """Detect volatility clustering."""
        if len(returns) < 20:
            return 0.5
        
        abs_returns = np.abs(returns)
        acf_lag1 = np.corrcoef(abs_returns[:-1], abs_returns[1:])[0, 1]
        
        if np.isnan(acf_lag1):
            acf_lag1 = 0.0
        
        return float(max(0.0, min(1.0, acf_lag1)))

    def _regularity_measure(self, prices: np.ndarray) -> float:
        """Measure price regularity."""
        if len(prices) < 20:
            return 0.5
        
        diffs = np.diff(prices)
        consecutive_dir = np.sum((diffs[:-1] * diffs[1:]) > 0) / (len(diffs) - 1)
        
        return float(consecutive_dir)

    def detect(self, ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Detect market complexity via fractal dimension."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        
        if len(closes) < 50:
            return {
                "signal": "NEUTRAL",
                "strength": 0.0,
                "fractal_dimension": 1.5,
                "complexity_level": "MODERATE",
            }
        
        fd = self._higuchi_fractal_dimension(closes)
        returns = np.log(closes[1:] / closes[:-1])
        vol_clustering = self._volatility_clustering(returns)
        regularity = self._regularity_measure(closes)
        
        if fd < self.complexity_threshold_low:
            complexity_level = "SIMPLE"
            strength = min(1.0, (self.complexity_threshold_low - fd) / 0.5)
            signal = "BULLISH"
        elif fd > self.complexity_threshold_high:
            complexity_level = "COMPLEX"
            strength = min(1.0, (fd - self.complexity_threshold_high) / 0.5)
            signal = "BEARISH"
        else:
            complexity_level = "MODERATE"
            strength = 0.5
            signal = "NEUTRAL"
        
        return {
            "signal": signal,
            "strength": float(strength),
            "fractal_dimension": float(fd),
            "complexity_level": complexity_level,
            "volatility_clustering": float(vol_clustering),
            "regularity": float(regularity),
        }
