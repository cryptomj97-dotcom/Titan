import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional


class CointegrationModel:
    """Cointegration detector for multi-asset pair trading strategies."""

    def __init__(self):
        self.lookback = 252
        self.zscore_threshold = 2.0

    def _calculate_price_ratio(self, prices1: np.ndarray, prices2: np.ndarray) -> np.ndarray:
        """Calculate price ratio between two assets."""
        if len(prices1) != len(prices2):
            min_len = min(len(prices1), len(prices2))
            prices1 = prices1[-min_len:]
            prices2 = prices2[-min_len:]
        
        ratio = prices1 / prices2.replace(0, 1e-10)
        return ratio

    def _test_stationarity(self, prices: np.ndarray) -> float:
        """Simple stationarity test via autocorrelation."""
        if len(prices) < 10:
            return 0.0
        
        diffs = np.diff(prices)
        acf_lag1 = np.corrcoef(diffs[:-1], diffs[1:])[0, 1]
        
        if np.isnan(acf_lag1):
            acf_lag1 = 0.5
        
        stationarity_score = 1.0 - abs(acf_lag1)
        return float(np.clip(stationarity_score, 0.0, 1.0))

    def _calculate_spread(self, prices1: np.ndarray, prices2: np.ndarray, lookback: int = 20) -> Dict[str, float]:
        """Calculate spread between two price series."""
        ratio = self._calculate_price_ratio(prices1, prices2)
        
        if len(ratio) < lookback:
            return {"current": 0.0, "mean": 0.0, "std": 1.0, "zscore": 0.0}
        
        recent_ratio = ratio[-lookback:]
        mean_ratio = np.mean(recent_ratio)
        std_ratio = np.std(recent_ratio)
        
        current_spread = ratio[-1] - mean_ratio
        zscore = current_spread / (std_ratio + 1e-10) if std_ratio > 0 else 0.0
        
        return {
            "current": float(current_spread),
            "mean": float(mean_ratio),
            "std": float(std_ratio),
            "zscore": float(zscore),
        }

    def detect_pair(self, ohlcv1: Dict[str, list], ohlcv2: Dict[str, list]) -> Dict[str, Any]:
        """Detect cointegration between two assets."""
        closes1 = np.array([c["close"] for c in ohlcv1["1D"]], dtype=float)
        closes2 = np.array([c["close"] for c in ohlcv2["1D"]], dtype=float)
        
        if len(closes1) < 50 or len(closes2) < 50:
            return {
                "is_cointegrated": False,
                "signal": "NEUTRAL",
                "strength": 0.0,
                "mean_reversion_score": 0.0,
            }
        
        min_len = min(len(closes1), len(closes2))
        closes1 = closes1[-min_len:]
        closes2 = closes2[-min_len:]
        
        ratio = self._calculate_price_ratio(closes1, closes2)
        stationarity = self._test_stationarity(ratio)
        spread = self._calculate_spread(closes1, closes2)
        
        is_cointegrated = stationarity > 0.6
        
        if is_cointegrated and abs(spread["zscore"]) > self.zscore_threshold:
            if spread["zscore"] > 0:
                signal = "SHORT_PAIR"
                strength = min(1.0, spread["zscore"] / (self.zscore_threshold * 2))
            else:
                signal = "LONG_PAIR"
                strength = min(1.0, abs(spread["zscore"]) / (self.zscore_threshold * 2))
        else:
            signal = "NEUTRAL"
            strength = 0.0
        
        return {
            "is_cointegrated": is_cointegrated,
            "signal": signal,
            "strength": float(strength),
            "stationarity_score": float(stationarity),
            "mean_reversion_score": float(stationarity),
            "spread": spread,
        }

    def detect_portfolio(self, asset_closes: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Detect cointegration across portfolio of assets (placeholder)."""
        if len(asset_closes) < 2:
            return {
                "cointegration_matrix": {},
                "portfolio_mean_reversion": 0.0,
                "hedging_pairs": [],
            }
        
        assets = list(asset_closes.keys())
        cointegration_matrix = {}
        hedging_pairs = []
        
        for i, asset1 in enumerate(assets):
            for asset2 in assets[i+1:]:
                closes1 = asset_closes[asset1]
                closes2 = asset_closes[asset2]
                
                min_len = min(len(closes1), len(closes2))
                ratio = closes1[-min_len:] / closes2[-min_len:].replace(0, 1e-10)
                stationarity = self._test_stationarity(ratio)
                
                pair_name = f"{asset1}-{asset2}"
                cointegration_matrix[pair_name] = float(stationarity)
                
                if stationarity > 0.65:
                    hedging_pairs.append({"pair": pair_name, "strength": stationarity})
        
        portfolio_mean_reversion = np.mean(list(cointegration_matrix.values())) if cointegration_matrix else 0.0
        
        return {
            "cointegration_matrix": cointegration_matrix,
            "portfolio_mean_reversion": float(portfolio_mean_reversion),
            "hedging_pairs": hedging_pairs,
        }
