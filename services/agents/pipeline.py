from typing import Callable

from services.agents.nodes.data_node import DataNode
from services.agents.nodes.debate_node import DebateNode
from services.agents.nodes.gate_node import GateNode
from services.agents.nodes.indicator_node import IndicatorNode
from services.agents.nodes.output_node import OutputNode
from services.agents.nodes.regime_node import RegimeNode
from services.agents.state import TitanState


class AgentPipeline:
    def __init__(self, publish_event: Callable[[str, dict], None]):
        self.publish_event = publish_event
        self.nodes = [
            DataNode(),
            RegimeNode(),
            IndicatorNode(),
            GateNode(),
            DebateNode(),
            OutputNode(),
        ]

    def run(self, state: TitanState) -> TitanState:
        self.publish_event("PIPELINE_STARTED", {
            "asset": state.asset,
            "asset_class": state.asset_class,
            "mode": state.mode,
        })

        for node in self.nodes:
            state = node.execute(state, self.publish_event)

        self.publish_event("PIPELINE_FINISHED", {
            "final_output": state.final_output,
            "debate": state.debate,
        })
        return state
