import numpy as np
import warnings
from typing import Dict, Any, Optional, Tuple

warnings.filterwarnings("ignore")


class HMMRegimeDetector:
    """HMM-based regime detection using Gaussian HMM."""

    def __init__(self, n_states: int = 3):
        self.n_states = n_states
        self.model = None
        self._is_trained = False

    def _validate_inputs(self, features: np.ndarray) -> np.ndarray:
        """Validate and clean input features."""
        features = np.asarray(features, dtype=float)
        if np.isnan(features).any():
            features = np.nan_to_num(features, nan=0.0)
        if np.isinf(features).any():
            features = np.clip(features, -1e6, 1e6)
        return features

    def fit(self, ohlcv: Dict[str, list], lookback: int = 252) -> None:
        """Fit HMM on historical returns and realized volatility."""
        closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)[-lookback:]
        
        if len(closes) < 20:
            self._is_trained = False
            return
        
        returns = np.log(closes[1:] / closes[:-1]) * 100
        
        realized_vol = []
        for i in range(len(returns)):
            start = max(0, i - 19)
            window_vol = np.std(returns[start:i+1]) if i > 0 else 1.0
            realized_vol.append(window_vol)
        
        realized_vol = np.array(realized_vol)
        
        features = np.column_stack([returns, realized_vol])
        features = self._validate_inputs(features)
        
        try:
            from hmmlearn.hmm import GaussianHMM
            self.model = GaussianHMM(n_components=self.n_states, covariance_type="full", n_iter=100, random_state=42)
            self.model.fit(features)
            self._is_trained = True
        except Exception as e:
            self._is_trained = False

    def predict(self, ohlcv: Dict[str, list]) -> Dict[str, Any]:
        """Predict current regime using HMM."""
        if not self._is_trained or self.model is None:
            return {
                "state": "UNKNOWN",
                "state_probabilities": {},
                "confidence": 0.0,
            }
        
        try:
            closes = np.array([c["close"] for c in ohlcv["1D"]], dtype=float)
            
            if len(closes) < 20:
                return {"state": "UNKNOWN", "state_probabilities": {}, "confidence": 0.0}
            
            returns = np.log(closes[-20:] / closes[-21:-1]) * 100
            realized_vol = np.std(returns) if len(returns) > 1 else 1.0
            
            recent_features = np.column_stack([returns, np.full_like(returns, realized_vol)])
            recent_features = self._validate_inputs(recent_features)
            
            state = self.model.predict(recent_features)[-1]
            score = self.model.score(recent_features)
            
            state_means = self.model.means_
            state_vols = [np.sqrt(np.diag(cov)[0]) for cov in self.model.covars_]
            
            sorted_indices = np.argsort(state_vols)
            state_mapping = {
                sorted_indices[2]: "HIGH_VOL_TREND",
                sorted_indices[1]: "LOW_VOL_TREND",
                sorted_indices[0]: "CHOPPY_RANGE",
            }
            
            regime_name = state_mapping.get(state, f"STATE_{state}")
            
            return {
                "state": regime_name,
                "state_probabilities": {f"STATE_{i}": float(prob) for i, prob in enumerate(self.model.predict_proba(recent_features)[-1])},
                "confidence": float(np.exp(score / len(recent_features))),
            }
        except Exception as e:
            return {"state": "UNKNOWN", "state_probabilities": {}, "confidence": 0.0}

    def get_consensus(self, statistical_regime: Dict[str, Any], hmm_regime: Dict[str, Any]) -> Dict[str, Any]:
        """Blend statistical and HMM results for consensus."""
        stat_regime = statistical_regime.get("regime", "UNKNOWN")
        hmm_state = hmm_regime.get("state", "UNKNOWN")
        
        stat_conf = statistical_regime.get("regime_confidence", 0.0)
        hmm_conf = hmm_regime.get("confidence", 0.0)
        
        if stat_regime == "UNKNOWN" or hmm_state == "UNKNOWN":
            return {
                "consensus_regime": "UNKNOWN",
                "consensus_confidence": 0.0,
                "agreement": False,
                "stat_regime": stat_regime,
                "hmm_regime": hmm_state,
            }
        
        agreement = (
            (stat_regime == "TRENDING" and "TREND" in hmm_state) or
            (stat_regime == "MEAN_REVERTING" and "RANGE" in hmm_state) or
            (stat_regime == "RANDOM_WALK")
        )
        
        if agreement:
            consensus_conf = (stat_conf + hmm_conf) / 2 * 1.1
        else:
            consensus_conf = (stat_conf + hmm_conf) / 2 * 0.7
        
        return {
            "consensus_regime": stat_regime if agreement else hmm_state,
            "consensus_confidence": min(0.95, consensus_conf),
            "agreement": agreement,
            "stat_regime": stat_regime,
            "hmm_regime": hmm_state,
        }
