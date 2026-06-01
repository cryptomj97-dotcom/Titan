from typing import Callable, Dict

from services.agents.state import TitanState
from services.quant.clusters.momentum import MomentumCluster
from services.quant.clusters.trend import TrendCluster
from services.quant.clusters.volatility_volume_sentiment import SentimentCluster, VolumeCluster, VolatilityCluster
from services.quant.confidence_scorer import ConfidenceScorer
from services.quant.indicator_matrix import IndicatorMatrix
from services.quant.ml.anomaly_detector import AnomalyDetector
from services.quant.ml.signal_scorer import LightGBMSignalScorer
from services.quant.statistical.autocorrelation import AutocorrelationModel
from services.quant.statistical.fractal import FractalModel
from services.quant.statistical.zscore import ZScoreModel


class IndicatorNode:
    def execute(self, state: TitanState, publish: Callable[[str, dict], None]) -> TitanState:
        packet = state.data_packet
        regime_name = state.regime["consensus"].get("consensus_regime", "UNKNOWN")

        trend = TrendCluster().detect(packet.ohlcv, regime_name)
        momentum = MomentumCluster().detect(packet.ohlcv, regime_name)
        volatility = VolatilityCluster().detect(packet.ohlcv)
        volume = VolumeCluster().detect(packet.ohlcv)

        social_payload = {}
        if packet.social_sentiment:
            social_payload = packet.social_sentiment.dict()

        funding_rate = 0.0
        if packet.crypto_metrics and getattr(packet.crypto_metrics, "funding_rate", None) is not None:
            funding_rate = float(packet.crypto_metrics.funding_rate)

        sentiment = SentimentCluster().detect(social_payload, funding_rate)

        statistical_models = {
            "zscore_model": ZScoreModel().detect(packet.ohlcv),
            "autocorrelation_model": AutocorrelationModel().detect(packet.ohlcv),
            "fractal_model": FractalModel().detect(packet.ohlcv),
        }

        cluster_signals = {
            "trend_cluster": trend,
            "momentum_cluster": momentum,
            "volatility_cluster": volatility,
            "volume_cluster": volume,
            "sentiment_cluster": sentiment,
        }

        active_indicators = IndicatorMatrix().get_active_indicators(
            state.asset_class,
            regime_name,
        )

        matrix_score = IndicatorMatrix().score_indicators({**cluster_signals, **statistical_models}, active_indicators)
        ml_score = LightGBMSignalScorer().score_signal(cluster_signals, state.regime["consensus"])
        anomaly_result = AnomalyDetector().validate_signal(cluster_signals, packet.ohlcv)

        backtest_edge = min(0.05, max(0.0, matrix_score.get("weighted_score", 0.5) * 0.03 + ml_score.get("ml_score", 0.5) * 0.02))

        confidence_score = ConfidenceScorer().score_signal(
            cluster_signals,
            state.regime["consensus"],
            statistical_models,
            ml_score,
            anomaly_result,
            backtest_edge,
        )

        state.clusters = cluster_signals
        state.statistical_models = statistical_models
        state.ml_score = ml_score
        state.anomaly_result = anomaly_result
        state.confidence_score = confidence_score
        state.final_output = {
            "cluster_matrix": matrix_score,
            "backtest_edge": backtest_edge,
        }

        publish("CLUSTERS_READY", {
            "clusters": cluster_signals,
            "statistical_models": statistical_models,
            "ml_score": ml_score,
            "anomaly_result": anomaly_result,
            "confidence_score": confidence_score,
            "matrix_score": matrix_score,
        })
        return state
