from typing import Callable

from services.agents.state import TitanState


class OutputNode:
    def execute(self, state: TitanState, publish: Callable[[str, dict], None]) -> TitanState:
        closes = state.data_packet.ohlcv["1D"]
        current_price = float(closes[-1]["close"]) if closes else 0.0
        signal = state.confidence_score.get("signal", "NEUTRAL")
        confidence = state.confidence_score.get("confidence", 0.0)
        position_size = state.confidence_score.get("confidence", 0.0)

        if signal == "BULLISH":
            trade_plan = {
                "entry": current_price,
                "stop_loss": float(current_price * 0.98),
                "target1": float(current_price * 1.04),
                "target2": float(current_price * 1.08),
                "position_size": position_size,
            }
        elif signal == "BEARISH":
            trade_plan = {
                "entry": current_price,
                "stop_loss": float(current_price * 1.02),
                "target1": float(current_price * 0.96),
                "target2": float(current_price * 0.92),
                "position_size": position_size,
            }
        else:
            trade_plan = {
                "entry": current_price,
                "stop_loss": None,
                "target1": None,
                "target2": None,
                "position_size": 0.0,
            }

        state.final_output = {
            "asset": state.asset,
            "signal": signal,
            "confidence": confidence,
            "position_size": position_size,
            "trade_plan": trade_plan,
            "analysis_mode": state.mode,
            "reason": "Quant + structured agent layer produced the final view.",
            "is_blocked": state.gate_result.get("is_blocked", False),
        }

        publish("OUTPUT_READY", state.final_output)
        return state
