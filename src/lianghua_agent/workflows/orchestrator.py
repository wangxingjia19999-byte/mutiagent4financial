from lianghua_agent.agents import build_workflow_graph
from lianghua_agent.agents.state import AgentGraphState
from lianghua_agent.models.schema import WorkflowResult, WorkflowState


class WorkflowOrchestrator:
    """Coordinate agent workflows."""

    def __init__(self):
        self.app = build_workflow_graph()

    def run(self, state: WorkflowState) -> WorkflowResult:
        graph_input: AgentGraphState = {"input_state": state}
        graph_output = self.app.invoke(graph_input)

        technical_result = graph_output["technical"]
        news_result = graph_output["news"]
        final_result = graph_output["final_decision"]

        return WorkflowResult(
            success=technical_result.success and news_result.success and final_result.success,
            message="workflow completed",
            technical=technical_result,
            news=news_result,
            final_decision=final_result,
        )
