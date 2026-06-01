from typing import Callable

from services.agents.state import TitanState
from services.quant.confidence_scorer import ConfidenceScorer


class GateNode:
    def execute(self, state: TitanState, publish: Callable[[str, dict], None]) -> TitanState:
        scorer = ConfidenceScorer()
        gate_result = scorer.apply_hard_stop(state.confidence_score.copy() if state.confidence_score else {})
        state.confidence_score = gate_result
        state.gate_result = {
            "is_blocked": gate_result.get("is_blocked", False),
            "block_reason": gate_result.get("block_reason"),
            "signal": gate_result.get("signal"),
            "confidence": gate_result.get("confidence"),
        }

        publish("GATE_EVALUATED", state.gate_result)
        return state
