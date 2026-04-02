from typing import Any
from typing_extensions import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .config import AgentSettings
from .prompt_manager import PromptManager


class AgentState(TypedDict, total=False):
    input: str
    context: dict[str, Any]
    messages: Annotated[list[BaseMessage], add_messages]
    output: str


class BaseAgent:
    """基础 Agent 类
    
    支持从 PromptManager 加载 prompt 模板，或者使用自定义 prompt
    """
    # 子类可以覆盖这个属性来指定使用的 prompt 模板
    prompt_template_name: str | None = None

    def __init__(self, settings: AgentSettings | None = None, system_prompt: str | None = None):
        self.settings = settings or AgentSettings.from_env()
        self._system_prompt = system_prompt
        self.llm = self._build_llm()
        self.graph = self._build_graph()

    def _build_llm(self) -> ChatOpenAI:
        headers: dict[str, str] = {}
        if self.settings.site_url:
            headers["HTTP-Referer"] = self.settings.site_url
        if self.settings.app_name:
            headers["X-Title"] = self.settings.app_name

        return ChatOpenAI(
            model=self.settings.model,
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            temperature=self.settings.temperature,
            default_headers=headers or None,
        )

    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """获取 system prompt
        
        优先级：
        1. 自定义 system_prompt（通过 __init__ 传入）
        2. PromptManager 中的模板（通过 prompt_template_name）
        3. 默认 prompt
        """
        if self._system_prompt:
            return self._system_prompt

        # 如果指定了模板名称，从 PromptManager 获取
        if self.prompt_template_name:
            try:
                context = context or {}
                return PromptManager.render_system_prompt(
                    self.prompt_template_name,
                    horizon=context.get("horizon", "1-3个月"),
                    risk_level=context.get("risk_level", "中等"),
                    strategy=context.get("strategy", "趋势跟随 + 风险控制"),
                )
            except ValueError as e:
                print(f"警告: 无法加载 prompt 模板 {self.prompt_template_name}: {e}")

        return "你是一个可靠的通用 AI 智能体，请根据输入完成高质量回答。"

    def build_messages(self, user_input: str, context: dict[str, Any] | None = None) -> list[BaseMessage]:
        system_prompt = self.get_system_prompt(context)
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ]

    def pre_invoke(self, state: AgentState) -> AgentState:
        return state

    def post_invoke(self, state: AgentState) -> AgentState:
        return state

    def _agent_node(self, state: AgentState) -> AgentState:
        user_input = state.get("input", "")
        context = state.get("context", {})
        messages = self.build_messages(user_input=user_input, context=context)
        response = self.llm.invoke(messages)

        text_output = self._extract_text(response)
        return {
            "messages": [response],
            "output": text_output,
        }

    @staticmethod
    def _extract_text(message: BaseMessage) -> str:
        if isinstance(message, AIMessage):
            if isinstance(message.content, str):
                return message.content
            if isinstance(message.content, list):
                return "\n".join(
                    str(block.get("text", block)) if isinstance(block, dict) else str(block)
                    for block in message.content
                )
        return str(message.content)

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._agent_node)
        workflow.add_edge(START, "agent")
        workflow.add_edge("agent", END)
        return workflow.compile()

    def invoke(self, user_input: str, context: dict[str, Any] | None = None) -> AgentState:
        initial_state: AgentState = {
            "input": user_input,
            "context": context or {},
        }
        prepared_state = self.pre_invoke(initial_state)
        result = self.graph.invoke(prepared_state)
        return self.post_invoke(result)
