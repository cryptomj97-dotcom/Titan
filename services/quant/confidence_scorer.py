import numpy as np
from typing import Dict, Any, List


class ConfidenceScorer:
    """Confidence scorer combining regime, clusters, statistical, and ML signals."""

    def __init__(self):
        self.min_cluster_consensus = 2
        self.hard_stop_threshold = -0.5

    def _normalize_confidence(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Normalize confidence to [0, 1]."""
        if value < min_val:
            return 0.0
        if value > max_val:
            return 1.0
        return (value - min_val) / (max_val - min_val)

    def _aggregate_cluster_signals(self, clusters: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate signals from all clusters."""
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        strength_scores = []
        
        for cluster_name, cluster_data in clusters.items():
            if isinstance(cluster_data, dict):
                signal = cluster_data.get("signal", "NEUTRAL")
                strength = cluster_data.get("strength", 0.5)
                strength_scores.append(strength)
                
                if signal == "BULLISH":
                    bullish_count += 1
                elif signal == "BEARISH":
                    bearish_count += 1
                else:
                    neutral_count += 1
        
        total_clusters = bullish_count + bearish_count + neutral_count
        
        bullish_pct = bullish_count / total_clusters if total_clusters > 0 else 0.0
        bearish_pct = bearish_count / total_clusters if total_clusters > 0 else 0.0
        
        avg_strength = np.mean(strength_scores) if strength_scores else 0.5
        
        if bullish_count >= self.min_cluster_consensus and bullish_pct > bearish_pct:
            consensus = "BULLISH"
            consensus_strength = bullish_pct
        elif bearish_count >= self.min_cluster_consensus and bearish_pct > bullish_pct:
            consensus = "BEARISH"
            consensus_strength = bearish_pct
        else:
            consensus = "NEUTRAL"
            consensus_strength = 0.0
        
        return {
            "consensus": consensus,
            "consensus_strength": consensus_strength,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "avg_strength": avg_strength,
        }

    def _score_regime_alignment(self, regime_info: Dict[str, Any], cluster_consensus: str) -> float:
        """Score how well cluster consensus aligns with regime."""
        regime = regime_info.get("regime", "UNKNOWN")
        confidence = regime_info.get("regime_confidence", 0.5)
        
        if regime == "UNKNOWN":
            return 0.5
        
        if regime == "TRENDING":
            if cluster_consensus in ["BULLISH", "BEARISH"]:
                return float(np.clip(confidence, 0.5, 1.0))
            else:
                return 0.5
        
        elif regime == "MEAN_REVERTING":
            if cluster_consensus == "NEUTRAL":
                return float(np.clip(confidence, 0.5, 1.0))
            else:
                return float(np.clip(confidence * 0.8, 0.3, 1.0))
        
        else:
            return 0.5

    def _combine_signal_scores(self, cluster_score: float, statistical_score: float, ml_score: float, anomaly_score: float) -> float:
        """Combine multiple signal scores with weighting."""
        cluster_weight = 0.35
        statistical_weight = 0.25
        ml_weight = 0.30
        anomaly_weight = 0.10
        
        combined = (
            cluster_score * cluster_weight +
            statistical_score * statistical_weight +
            ml_score * ml_weight +
            (1.0 - anomaly_score) * anomaly_weight
        )
        
        return float(combined)

    def score_signal(
        self,
        clusters: Dict[str, Dict[str, Any]],
        regime_info: Dict[str, Any],
        statistical_models: Dict[str, Dict[str, Any]],
        ml_score: Dict[str, Any],
        anomaly_result: Dict[str, Any],
        backtest_edge: float = 0.0,
    ) -> Dict[str, Any]:
        """Generate final confidence score for signal."""
        
        cluster_agg = self._aggregate_cluster_signals(clusters)
        regime_alignment = self._score_regime_alignment(regime_info, cluster_agg["consensus"])
        
        cluster_score = float(np.clip(cluster_agg["avg_strength"] * regime_alignment, 0.0, 1.0))
        
        stat_signals = []
        for model_name, model_data in statistical_models.items():
            if isinstance(model_data, dict) and "strength" in model_data:
                stat_signals.append(model_data["strength"])
        
        statistical_score = np.mean(stat_signals) if stat_signals else 0.5
        statistical_score = float(np.clip(statistical_score, 0.0, 1.0))
        
        ml_probability = ml_score.get("ml_score", 0.5)
        ml_score_val = float(np.clip(ml_probability, 0.0, 1.0))
        
        anomaly_score = anomaly_result.get("anomaly_score", 0.0)
        
        combined_confidence = self._combine_signal_scores(
            cluster_score,
            statistical_score,
            ml_score_val,
            anomaly_score
        )
        
        backtest_multiplier = 1.0 + (backtest_edge * 10.0) if backtest_edge > 0 else 1.0
        final_confidence = combined_confidence * backtest_multiplier
        final_confidence = float(np.clip(final_confidence, 0.0, 1.0))
        
        if cluster_agg["consensus"] == "BULLISH":
            signal = "BULLISH"
        elif cluster_agg["consensus"] == "BEARISH":
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"
        
        anomaly_severity = anomaly_result.get("severity", "NORMAL")
        if anomaly_severity == "CRITICAL":
            signal = "NEUTRAL"
            final_confidence = 0.0
        
        if not anomaly_result.get("is_valid", True):
            final_confidence = final_confidence * (1.0 - anomaly_result.get("confidence_reduction", 0.3))
        
        return {
            "signal": signal,
            "confidence": final_confidence,
            "cluster_consensus": cluster_agg["consensus"],
            "cluster_strength": float(cluster_agg["consensus_strength"]),
            "regime_alignment": float(regime_alignment),
            "statistical_score": float(statistical_score),
            "ml_score": float(ml_score_val),
            "anomaly_score": float(anomaly_score),
            "combined_confidence": float(combined_confidence),
            "backtest_edge": float(backtest_edge),
            "anomaly_severity": anomaly_severity,
            "breakout_status": "STRONG" if final_confidence > 0.75 else "MODERATE" if final_confidence > 0.5 else "WEAK",
        }

    def apply_hard_stop(self, confidence_score: Dict[str, Any]) -> Dict[str, Any]:
        """Apply hard-stop rules to filter invalid signals."""
        signal = confidence_score["signal"]
        confidence = confidence_score["confidence"]
        anomaly_score = confidence_score["anomaly_score"]
        regime_alignment = confidence_score["regime_alignment"]
        
        is_blocked = False
        block_reason = None
        
        if anomaly_score > 0.8:
            is_blocked = True
            block_reason = "CRITICAL_ANOMALY"
        
        if regime_alignment < 0.3 and confidence < 0.5:
            is_blocked = True
            block_reason = "REGIME_MISALIGNMENT"
        
        if signal == "NEUTRAL" and confidence < 0.3:
            is_blocked = True
            block_reason = "LOW_CONVICTION"
        
        confidence_score["is_blocked"] = is_blocked
        confidence_score["block_reason"] = block_reason
        
        if is_blocked:
            confidence_score["signal"] = "NEUTRAL"
            confidence_score["confidence"] = 0.0
        
        return confidence_score

    def get_position_sizing(self, confidence: float, max_position: float = 1.0) -> float:
        """Determine position size based on confidence."""
        if confidence < 0.3:
            return 0.0
        elif confidence < 0.5:
            return max_position * 0.25
        elif confidence < 0.65:
            return max_position * 0.5
        elif confidence < 0.8:
            return max_position * 0.75
        else:
            return max_position
