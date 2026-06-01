import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class TrendCluster:
    """Trend signal cluster using EMA crossover and MACD."""

    def __init__(self):
        self.ema_fast = 20
        self.ema_slow = 50
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

    def _ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate exponential moving average."""
        if len(prices) < period:
            return np.full_like(prices, prices[0], dtype=float)
        return pd.Series(prices).ewm(span=period, adjust=False).mean().values

    def _calculate_macd(self, closes: np.ndarray) -> Dict[str, Any]:
        """Calculate MACD indicator."""
        if len(closes) < self.macd_slow + self.macd_signal:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
        
        ema12 = self._ema(closes, self.macd_fast)
        ema26 = self._ema(closes, self.macd_slow)
        macd_line = ema12 - ema26
        signal_line = self._ema(macd_line, self.macd_signal)
        histogram = macd_line - signal_line
        
        return {
            "macd": float(macd_line[-1]),
            "signal": float(signal_line[-1]),
            "histogram": float(histogram[-1]),
        }

    def detect(self, ohlcv: Dict[str, list], regime: str) -> Dict[str, Any]:
        """Detect trend signals."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        
        if len(closes) < self.ema_slow:
            return {"signal": "NEUTRAL", "strength": 0.0}
        
        ema_fast = self._ema(closes, self.ema_fast)
        ema_slow = self._ema(closes, self.ema_slow)
        
        macd_data = self._calculate_macd(closes)
        
        current_fast = ema_fast[-1]
        current_slow = ema_slow[-1]
        
        if current_fast > current_slow and macd_data["histogram"] > 0:
            signal = "BULLISH"
            strength = min(1.0, (current_fast - current_slow) / current_slow)
        elif current_fast < current_slow and macd_data["histogram"] < 0:
            signal = "BEARISH"
            strength = min(1.0, (current_slow - current_fast) / current_slow)
        else:
            signal = "NEUTRAL"
            strength = 0.5
        
        return {
            "signal": signal,
            "strength": float(strength),
            "ema_fast": float(current_fast),
            "ema_slow": float(current_slow),
            "macd": macd_data,
        }
