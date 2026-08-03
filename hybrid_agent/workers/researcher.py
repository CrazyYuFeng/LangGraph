"""Researcher Worker —— Web 搜索智能体

职责：通过 Tavily 搜索互联网，获取实时信息、资料、新闻。
实现：基于 langchain.agents 的 create_agent，内部 ReAct 循环。
"""
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
from tools.web_search import get_web_search_tool
from mock_helpers import is_mock_mode, run_tool_and_reply


class ResearcherAgent:
    """Researcher 智能体：mock 模式下直接调用搜索工具，真实模式走 ReAct。"""

    def __init__(self):
        self.mock = is_mock_mode()
        self.tool = get_web_search_tool()
        if not self.mock:
            llm = ChatOpenAI(
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                temperature=0,
            )
            self.agent = create_agent(llm, [self.tool], name="researcher")

    def invoke(self, state):
        if self.mock:
            query = state["messages"][-1].content
            return run_tool_and_reply(self.tool, {"query": query})
        return self.agent.invoke(state)


def build_researcher():
    """构建 Researcher 智能体节点。"""
    return ResearcherAgent()
