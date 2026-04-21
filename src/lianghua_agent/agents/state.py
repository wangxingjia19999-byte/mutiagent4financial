from typing import TypedDict

from lianghua_agent.models.schema import (
    FinalDecisionResult,
    NewsAnalysisResult,
    TechnicalAnalysisResult,
    WorkflowState,
)


class AgentGraphState(TypedDict, total=False):
    input_state: WorkflowState
    technical: TechnicalAnalysisResult
    news: NewsAnalysisResult
    final_decision: FinalDecisionResult
