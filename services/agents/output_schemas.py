from typing import Dict, List

from pydantic import BaseModel, Field


class BullOutput(BaseModel):
    summary: str
    evidence: List[str]
    downside_risks: List[str]
    trade_bias: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    position_size: float = Field(..., ge=0.0, le=1.0)

    class Config:
        extra = "forbid"


class BearOutput(BaseModel):
    summary: str
    concerns: List[str]
    invalidation_points: List[str]
    conviction: float = Field(..., ge=0.0, le=1.0)
    evidence: List[str]

    class Config:
        extra = "forbid"


class JudgeOutput(BaseModel):
    verdict: str
    bull_score: int
    bear_score: int
    evidence_quality: Dict[str, int]
    logical_coherence: Dict[str, int]
    risk_acknowledgment: Dict[str, int]
    quant_alignment: Dict[str, int]
    key_risk: str
    rationale: str
    position_modifier: float = Field(..., ge=0.0, le=1.0)

    class Config:
        extra = "forbid"
