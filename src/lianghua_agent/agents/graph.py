from langgraph.graph import END, START, StateGraph

from lianghua_agent.agents.nodes import news_node, synthesis_node, technical_node
from lianghua_agent.agents.state import AgentGraphState


def build_workflow_graph():
    graph = StateGraph(AgentGraphState)

    graph.add_node("technical", technical_node)
    graph.add_node("news", news_node)
    graph.add_node("synthesis", synthesis_node)

    graph.add_edge(START, "technical")
    graph.add_edge(START, "news")
    graph.add_edge("technical", "synthesis")
    graph.add_edge("news", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()
