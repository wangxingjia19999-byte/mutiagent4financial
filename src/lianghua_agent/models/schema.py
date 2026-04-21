from typing import Literal

from pydantic import BaseModel, Field


ActionType = Literal["buy", "sell", "hold", "watch"]
TrendType = Literal["bullish", "bearish", "sideways"]
SentimentType = Literal["positive", "negative", "neutral"]


class WorkflowState(BaseModel):
    symbol: str
    timeframe: str = "1d"
    candles: list[dict] = Field(default_factory=list)
    indicators: dict = Field(default_factory=dict)
    news_items: list[dict] = Field(default_factory=list)
    risk_profile: str = "balanced"
    constraints: dict = Field(default_factory=dict)


class AgentNodeResult(BaseModel):
    success: bool = True
    message: str = ""


class TechnicalAnalysisResult(AgentNodeResult):
    trend: TrendType = "sideways"
    signal: ActionType = "watch"
    key_levels: list[float] = Field(default_factory=list)
    confidence: float = 0.0
    factor_refs: list[str] = Field(default_factory=list)
    factor_formulas: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class NewsAnalysisResult(AgentNodeResult):
    sentiment: SentimentType = "neutral"
    signal: ActionType = "watch"
    event_tags: list[str] = Field(default_factory=list)
    impact_horizon: str = "short"
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class ConflictResolution(BaseModel):
    has_conflict: bool = False
    strategy: str = "align"
    notes: str = ""


class FinalDecisionResult(AgentNodeResult):
    action: ActionType = "watch"
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    position_hint: str = "no_position"
    ttl: str = "1d"
    summary: str = ""
    conflict_info: ConflictResolution = Field(default_factory=ConflictResolution)


class WorkflowResult(AgentNodeResult):
    technical: TechnicalAnalysisResult
    news: NewsAnalysisResult
    final_decision: FinalDecisionResult
