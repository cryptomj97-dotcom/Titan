import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List


class RegimeDetector:
    """Statistical regime detection using Hurst exponent, ADX, and ATR."""

    def __init__(self):
        self.hurst_windows = [10, 20, 50, 100]
        self.atr_period = 14
        self.lookback = 252

    def _hurst_exponent(self, returns: np.ndarray, window: int) -> float:
        """Calculate rescaled range Hurst exponent using multiple window sizes."""
        if len(returns) < window:
            return 0.5

        sizes = [min(len(returns), x) for x in [20, 50, 100, len(returns)]]
        sizes = sorted(set(size for size in sizes if size >= 10))
        log_n = []
        log_rs = []

        for size in sizes:
            segment = returns[:size]
            mean_seg = np.mean(segment)
            Y = np.cumsum(segment - mean_seg)
            R = np.max(Y) - np.min(Y)
            S = np.std(segment, ddof=1)
            if S <= 0 or R <= 0:
                continue
            log_n.append(np.log(size))
            log_rs.append(np.log(R / S))

        if len(log_n) < 2:
            return 0.5

        try:
            slope = np.polyfit(log_n, log_rs, 1)[0]
            return float(np.clip(slope, 0.0, 1.0))
        except Exception:
            return 0.5

    def _calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
        """Calculate Average True Range."""
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = pd.Series(tr).rolling(self.atr_period).mean().values
        return atr

    def _calculate_adx(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> float:
        """Calculate ADX indicator (simplified)."""
        plus_dm = np.maximum(high - np.roll(high, 1), 0)
        minus_dm = np.maximum(np.roll(low, 1) - low, 0)
        
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        atr = pd.Series(tr).rolling(self.atr_period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(self.atr_period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(self.atr_period).mean() / atr
        
        di_sum = plus_di + minus_di
        di_diff = (plus_di - minus_di).abs()
        dx = 100 * di_diff / di_sum
        adx = pd.Series(dx).rolling(14).mean()
        
        return adx.iloc[-1] if len(adx) > 0 else 20.0

    def detect(self, ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Detect market regime using statistical methods."""
        
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        highs = np.array([c["high"] for c in ohlcv["1D"]], dtype=float)
        lows = np.array([c["low"] for c in ohlcv["1D"]], dtype=float)
        
        if len(closes) < 100:
            return {
                "regime": "UNKNOWN",
                "regime_confidence": 0.0,
                "stability_score": 0.0,
                "hurst": 0.5,
                "adx": 20.0,
                "volatility_percentile": 50.0,
            }
        
        returns = np.log(closes[1:] / closes[:-1])
        
        hurst_values = [self._hurst_exponent(returns, w) for w in self.hurst_windows]
        avg_hurst = np.mean(hurst_values)
        
        adx = self._calculate_adx(highs, lows, closes)
        
        atr_values = self._calculate_atr(highs, lows, closes)
        current_atr = atr_values[-1] if not np.isnan(atr_values[-1]) else np.nanmean(atr_values)
        atr_percentile = 100 * np.sum(atr_values[:-1] < current_atr) / len(atr_values[:-1]) if len(atr_values) > 1 else 50
        
        if avg_hurst > 0.55:
            regime = "TRENDING"
            confidence = min(0.95, 0.5 + (avg_hurst - 0.5))
        elif avg_hurst < 0.45:
            regime = "MEAN_REVERTING"
            confidence = min(0.95, 0.5 + (0.5 - avg_hurst))
        else:
            regime = "RANDOM_WALK"
            confidence = 0.5
        
        closes_close = closes[-10:]
        consecutive_up = np.sum(np.diff(closes_close) > 0)
        stability = consecutive_up / 9.0
        
        return {
            "regime": regime,
            "regime_confidence": float(confidence),
            "stability_score": float(stability),
            "hurst": float(avg_hurst),
            "adx": float(adx),
            "volatility_percentile": float(atr_percentile),
        }
