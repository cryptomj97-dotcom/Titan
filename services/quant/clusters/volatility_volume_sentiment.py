import numpy as np
import pandas as pd
from typing import Dict, Any


class VolatilityCluster:
    """Volatility signal cluster using Bollinger Bands and ATR."""

    def __init__(self):
        self.bb_period = 20
        self.bb_std = 2.0
        self.atr_period = 14

    def _calculate_bollinger_bands(self, closes: np.ndarray) -> Dict[str, float]:
        """Calculate Bollinger Bands."""
        if len(closes) < self.bb_period:
            mid = closes[-1] if len(closes) > 0 else 0.0
            return {"upper": mid * 1.05, "middle": mid, "lower": mid * 0.95}
        
        sma = pd.Series(closes).rolling(self.bb_period).mean()
        std = pd.Series(closes).rolling(self.bb_period).std()
        
        upper = sma + self.bb_std * std
        lower = sma - self.bb_std * std
        
        return {
            "upper": float(upper.iloc[-1]) if not pd.isna(upper.iloc[-1]) else closes[-1] * 1.05,
            "middle": float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else closes[-1],
            "lower": float(lower.iloc[-1]) if not pd.isna(lower.iloc[-1]) else closes[-1] * 0.95,
        }

    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> float:
        """Calculate Average True Range."""
        tr1 = highs - lows
        tr2 = np.abs(highs - np.roll(closes, 1))
        tr3 = np.abs(lows - np.roll(closes, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = pd.Series(tr).rolling(self.atr_period).mean()
        return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else np.mean(tr[-self.atr_period:])

    def detect(self, ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Detect volatility signals."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        highs = np.array([c["high"] for c in ohlcv["1D"]], dtype=float)
        lows = np.array([c["low"] for c in ohlcv["1D"]], dtype=float)
        
        current_close = closes[-1]
        bb = self._calculate_bollinger_bands(closes)
        atr = self._calculate_atr(highs, lows, closes)
        
        position = (current_close - bb["lower"]) / (bb["upper"] - bb["lower"]) if bb["upper"] != bb["lower"] else 0.5
        
        if position > 0.9:
            signal = "BEARISH"
            strength = min(1.0, (position - 0.9) * 10)
        elif position < 0.1:
            signal = "BULLISH"
            strength = min(1.0, (0.1 - position) * 10)
        else:
            if closes[-1] > closes[-2]:
                signal = "NEUTRAL"
            else:
                signal = "NEUTRAL"
            strength = 0.5
        
        atr_ratio = atr / current_close if current_close > 0 else 0.0
        
        return {
            "signal": signal,
            "strength": float(strength),
            "bollinger_bands": bb,
            "atr": float(atr),
            "atr_ratio": float(atr_ratio),
            "bb_position": float(position),
        }


class VolumeCluster:
    """Volume signal cluster using VWAP and OBV."""

    def __init__(self):
        self.vwap_period = 20
        self.obv_period = 14

    def _calculate_vwap(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> float:
        """Calculate Volume Weighted Average Price."""
        if len(closes) < self.vwap_period:
            return closes[-1]
        
        typical_price = (highs + lows + closes) / 3
        cum_vol_price = np.cumsum(typical_price * volumes)
        cum_vol = np.cumsum(volumes)
        
        vwap = cum_vol_price[-self.vwap_period:] / cum_vol[-self.vwap_period:]
        return float(vwap[-1]) if len(vwap) > 0 else closes[-1]

    def _calculate_obv(self, closes: np.ndarray, volumes: np.ndarray) -> float:
        """Calculate On-Balance Volume."""
        obv = np.zeros_like(closes, dtype=float)
        obv[0] = volumes[0]
        
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                obv[i] = obv[i-1] + volumes[i]
            elif closes[i] < closes[i-1]:
                obv[i] = obv[i-1] - volumes[i]
            else:
                obv[i] = obv[i-1]
        
        obv_ma = pd.Series(obv).rolling(self.obv_period).mean()
        return float(obv_ma.iloc[-1]) if not pd.isna(obv_ma.iloc[-1]) else float(obv[-1])

    def detect(self, ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Detect volume signals."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
        highs = np.array([c["high"] for c in ohlcv["1D"]], dtype=float)
        lows = np.array([c["low"] for c in ohlcv["1D"]], dtype=float)
        volumes = np.array([c.get("volume", 1) for c in ohlcv["1D"]], dtype=float)
        
        vwap = self._calculate_vwap(highs, lows, closes, volumes)
        obv = self._calculate_obv(closes, volumes)
        
        price_vs_vwap = closes[-1] - vwap
        
        if price_vs_vwap > 0 and obv > 0:
            signal = "BULLISH"
            strength = min(1.0, abs(price_vs_vwap) / vwap)
        elif price_vs_vwap < 0 and obv < 0:
            signal = "BEARISH"
            strength = min(1.0, abs(price_vs_vwap) / vwap)
        else:
            signal = "NEUTRAL"
            strength = 0.5
        
        return {
            "signal": signal,
            "strength": float(strength),
            "vwap": float(vwap),
            "obv": float(obv),
            "price_vs_vwap": float(price_vs_vwap),
        }


class SentimentCluster:
    """Sentiment signal cluster using news/social sentiment."""

    def detect(self, social_sentiment: Dict[str, Any], funding_rate: float = 0.0) -> Dict[str, Any]:
        """Detect sentiment signals."""
        if not social_sentiment:
            return {"signal": "NEUTRAL", "strength": 0.0}
        
        composite = social_sentiment.get("composite_score", 0.0)
        bullish_pct = social_sentiment.get("bullish_pct", 0.33)
        bearish_pct = social_sentiment.get("bearish_pct", 0.33)
        
        sentiment_score = composite + (funding_rate * 2)
        
        if sentiment_score > 0.2 and bullish_pct > 0.4:
            signal = "BULLISH"
            strength = min(1.0, (sentiment_score + bullish_pct) / 1.5)
        elif sentiment_score < -0.2 and bearish_pct > 0.4:
            signal = "BEARISH"
            strength = min(1.0, (abs(sentiment_score) + bearish_pct) / 1.5)
        else:
            signal = "NEUTRAL"
            strength = 0.5
        
        return {
            "signal": signal,
            "strength": float(strength),
            "composite_score": float(composite),
            "bullish_pct": float(bullish_pct),
            "bearish_pct": float(bearish_pct),
            "funding_rate": float(funding_rate),
        }
