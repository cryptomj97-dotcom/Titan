from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class NewsArticle(BaseModel):
    source: str
    title: str
    link: str
    published_at: str
    sentiment: float
    summary: Optional[str] = None


class SocialSentimentResult(BaseModel):
    source: str
    symbol: str
    composite_score: float
    bullish_pct: float
    bearish_pct: float
    neutral_pct: float
    mention_count: int


class CryptoSpecificMetrics(BaseModel):
    symbol: str
    funding_rate: Optional[float] = None
    funding_history: Optional[List[Dict[str, Any]]] = None
    open_interest: Optional[float] = None
    open_interest_change_pct: Optional[float] = None


class MacroSnapshot(BaseModel):
    fed_rate: Optional[float] = None
    treasury_10y: Optional[float] = None
    next_fomc_date: Optional[str] = None
    days_to_fomc: Optional[int] = None


class DataPacket(BaseModel):
    asset: str
    asset_class: str
    ohlcv: Dict[str, Any]
    news: List[NewsArticle]
    social_sentiment: Optional[SocialSentimentResult]
    crypto_metrics: Optional[CryptoSpecificMetrics]
    macro: MacroSnapshot
    quality_report: Dict[str, Any]
    assembled_at: str
