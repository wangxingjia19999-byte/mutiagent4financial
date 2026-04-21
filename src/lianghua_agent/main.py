from lianghua_agent.models.schema import WorkflowState
from lianghua_agent.workflows.orchestrator import WorkflowOrchestrator


def main() -> None:
    """Entry point for the agent application."""
    orchestrator = WorkflowOrchestrator()
    state = WorkflowState(
        symbol="000001.SZ",
        timeframe="1d",
        candles=[
            {"open": 10.1, "high": 10.5, "low": 9.9, "close": 10.0},
            {"open": 10.0, "high": 10.8, "low": 9.95, "close": 10.6},
        ],
        indicators={"ma_short": 10.4, "ma_long": 10.1},
        news_items=[
            {"title": "公司发布超预期财报", "content": "盈利增长，机构上调评级"},
        ],
        risk_profile="balanced",
    )

    result = orchestrator.run(state)
    print(result.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
