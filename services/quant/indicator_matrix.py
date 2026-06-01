import numpy as np
from typing import Dict, Any, List


class IndicatorMatrix:
    """Indicator matrix for asset class and regime-specific signal selection."""

    def __init__(self):
        self.matrix = self._build_matrix()

    def _build_matrix(self) -> Dict[str, Dict[str, List[str]]]:
        """Build indicator selection matrix for different asset classes and regimes."""
        return {
            "CRYPTO": {
                "TRENDING": [
                    "trend_cluster",
                    "momentum_cluster",
                    "sentiment_cluster",
                    "fractal_model",
                ],
                "MEAN_REVERTING": [
                    "momentum_cluster",
                    "autocorrelation_model",
                    "volatility_cluster",
                    "zscore_model",
                ],
                "RANDOM_WALK": [
                    "volatility_cluster",
                    "volume_cluster",
                    "zscore_model",
                ],
            },
            "EQUITY": {
                "TRENDING": [
                    "trend_cluster",
                    "volume_cluster",
                    "momentum_cluster",
                    "zscore_model",
                ],
                "MEAN_REVERTING": [
                    "momentum_cluster",
                    "autocorrelation_model",
                    "volatility_cluster",
                ],
                "RANDOM_WALK": [
                    "volatility_cluster",
                    "volume_cluster",
                ],
            },
            "FOREX": {
                "TRENDING": [
                    "trend_cluster",
                    "momentum_cluster",
                    "fractal_model",
                ],
                "MEAN_REVERTING": [
                    "autocorrelation_model",
                    "zscore_model",
                    "volatility_cluster",
                ],
                "RANDOM_WALK": [
                    "volatility_cluster",
                    "zscore_model",
                ],
            },
        }

    def get_active_indicators(self, asset_class: str, regime: str) -> List[str]:
        """Get active indicators for asset class and regime combination."""
        asset_class = asset_class.upper()
        regime = regime.upper()
        
        if asset_class not in self.matrix:
            asset_class = "CRYPTO"
        
        if regime not in self.matrix[asset_class]:
            regime = "RANDOM_WALK"
        
        return self.matrix[asset_class][regime]

    def score_indicators(
        self,
        signals: Dict[str, Dict[str, Any]],
        active_indicators: List[str],
    ) -> Dict[str, Any]:
        """Score using only active indicators for regime/asset class."""
        weighted_signals = []
        weights = []
        
        weights_map = {
            "trend_cluster": 0.25,
            "momentum_cluster": 0.25,
            "volatility_cluster": 0.15,
            "volume_cluster": 0.15,
            "sentiment_cluster": 0.10,
            "zscore_model": 0.10,
            "autocorrelation_model": 0.15,
            "fractal_model": 0.12,
        }
        
        for indicator_name in active_indicators:
            if indicator_name in signals and isinstance(signals[indicator_name], dict):
                signal_data = signals[indicator_name]
                strength = signal_data.get("strength", 0.5)
                
                weight = weights_map.get(indicator_name, 0.1)
                
                weighted_signals.append(strength)
                weights.append(weight)
        
        if not weighted_signals:
            return {
                "weighted_score": 0.5,
                "indicator_count": 0,
                "active_count": len(active_indicators),
            }
        
        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = 1.0
        
        normalized_weights = [w / total_weight for w in weights]
        weighted_score = sum(s * w for s, w in zip(weighted_signals, normalized_weights))
        
        return {
            "weighted_score": float(np.clip(weighted_score, 0.0, 1.0)),
            "indicator_count": len(weighted_signals),
            "active_count": len(active_indicators),
            "coverage": len(weighted_signals) / len(active_indicators) if active_indicators else 0.0,
        }

    def get_matrix_view(self) -> Dict[str, Any]:
        """Get readable view of the indicator matrix."""
        view = {}
        for asset_class, regime_dict in self.matrix.items():
            view[asset_class] = {}
            for regime, indicators in regime_dict.items():
                view[asset_class][regime] = {
                    "indicators": indicators,
                    "count": len(indicators),
                }
        return view
