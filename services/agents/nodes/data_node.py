from typing import Callable

from services.agents.state import TitanState


class DataNode:
    def execute(self, state: TitanState, publish: Callable[[str, dict], None]) -> TitanState:
        publish("DATA_NODE_COMPLETE", {
            "asset": state.asset,
            "asset_class": state.asset_class,
            "quality_report": state.data_packet.quality_report,
        })
        return state
