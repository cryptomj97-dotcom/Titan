import numpy as np
import pandas as pd
from typing import Dict, Any


class MomentumCluster:
    """Momentum signal cluster using RSI and Stochastic."""

    def __init__(self):
        self.rsi_period = 14
        self.stoch_k = 14
        self.stoch_d = 3
        self.rsi_overbought = 70
        self.rsi_oversold = 30

    def _calculate_rsi(self, prices: np.ndarray) -> np.ndarray:
        """Calculate RSI indicator."""
        if len(prices) < self.rsi_period:
            return np.full_like(prices, 50.0)
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = pd.Series(gains).rolling(self.rsi_period).mean()
        avg_loss = pd.Series(losses).rolling(self.rsi_period).mean()
        
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50).values

    def _detect_divergence(self, prices: np.ndarray, rsi: np.ndarray, lookback: int = 20) -> str:
        """Detect RSI divergence."""
        if len(prices) < lookback or len(rsi) < lookback:
            return "NONE"
        
        recent_prices = prices[-lookback:]
        recent_rsi = rsi[-lookback:]
        
        price_higher = recent_prices[-1] > np.mean(recent_prices[:-5])
        rsi_lower = recent_rsi[-1] < np.mean(recent_rsi[:-5])
        
        if price_higher and rsi_lower:
            return "BULLISH"
        
        price_lower = recent_prices[-1] < np.mean(recent_prices[:-5])
        rsi_higher = recent_rsi[-1] > np.mean(recent_rsi[:-5])
        
        if price_lower and rsi_higher:
            return "BEARISH"
        
        return "NONE"

    def _calculate_stochastic(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Dict[str, float]:
        """Calculate Stochastic oscillator."""
        if len(closes) < self.stoch_k:
            return {"k": 50.0, "d": 50.0}
        
        lowest_low = pd.Series(lows).rolling(self.stoch_k).min()
        highest_high = pd.Series(highs).rolling(self.stoch_k).max()
        
        k_line = 100 * (closes - lowest_low) / (highest_high - lowest_low).replace(0, 1e-10)
        d_line = k_line.rolling(self.stoch_d).mean()
        
        return {
            "k": float(k_line.iloc[-1]) if not pd.isna(k_line.iloc[-1]) else 50.0,
            "d": float(d_line.iloc[-1]) if not pd.isna(d_line.iloc[-1]) else 50.0,
        }

    def detect(self, ohlcv: Dict[str, list], regime: str) -> Dict[str, Any]:
        """Detect momentum signals."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        highs = np.array([c["high"] for c in ohlcv["1D"]], dtype=float)
        lows = np.array([c["low"] for c in ohlcv["1D"]], dtype=float)
        
        if len(closes) < self.rsi_period:
            return {"signal": "NEUTRAL", "strength": 0.0}
        
        rsi = self._calculate_rsi(closes)
        current_rsi = rsi[-1]
        
        stoch = self._calculate_stochastic(highs, lows, closes)
        divergence = self._detect_divergence(closes, rsi)
        
        if regime == "RANGING":
            if current_rsi > self.rsi_overbought:
                signal = "BEARISH"
                strength = min(1.0, (current_rsi - self.rsi_overbought) / 30)
            elif current_rsi < self.rsi_oversold:
                signal = "BULLISH"
                strength = min(1.0, (self.rsi_oversold - current_rsi) / 30)
            else:
                signal = "NEUTRAL"
                strength = 0.5
        else:
            if current_rsi > 50 and divergence == "BULLISH":
                signal = "BULLISH"
                strength = 0.8
            elif current_rsi < 50 and divergence == "BEARISH":
                signal = "BEARISH"
                strength = 0.8
            else:
                signal = "NEUTRAL"
                strength = 0.5
        
        return {
            "signal": signal,
            "strength": float(strength),
            "rsi": float(current_rsi),
            "stochastic": stoch,
            "divergence": divergence,
        }
