from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from services.data.schemas import DataPacket


class TitanState(BaseModel):
    analysis_id: int
    asset: str
    asset_class: str
    mode: str
    data_packet: DataPacket
    regime: Optional[Dict[str, Any]] = None
    clusters: Optional[Dict[str, Any]] = None
    statistical_models: Optional[Dict[str, Any]] = None
    ml_score: Optional[Dict[str, Any]] = None
    anomaly_result: Optional[Dict[str, Any]] = None
    confidence_score: Optional[Dict[str, Any]] = None
    gate_result: Optional[Dict[str, Any]] = None
    debate: Optional[Dict[str, Any]] = None
    final_output: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    errors: list[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
