from typing import Callable

from services.agents.state import TitanState
from services.quant.ml.hmm_regime import HMMRegimeDetector
from services.quant.regime_detector import RegimeDetector


class RegimeNode:
    def execute(self, state: TitanState, publish: Callable[[str, dict], None]) -> TitanState:
        statistical = RegimeDetector().detect(state.data_packet.ohlcv)
        hmm_detector = HMMRegimeDetector()
        hmm_detector.fit(state.data_packet.ohlcv)
        hmm_result = hmm_detector.predict(state.data_packet.ohlcv)
        consensus = hmm_detector.get_consensus(statistical, hmm_result)

        state.regime = {
            "statistical": statistical,
            "hmm": hmm_result,
            "consensus": consensus,
        }

        publish("REGIME_DETECTED", {
            "statistical": statistical,
            "hmm": hmm_result,
            "consensus": consensus,
        })
        return state
