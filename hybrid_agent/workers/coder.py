"""Coder Worker —— Python 代码执行智能体

职责：通过 Python REPL 执行代码，处理数学计算、数据分析、脚本任务。
实现：基于 langchain.agents 的 create_agent，内部 ReAct 循环。
"""
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
from tools.python_repl import python_repl
from mock_helpers import is_mock_mode, run_tool_and_reply


class CoderAgent:
    """Coder 智能体：mock 模式下直接执行代码，真实模式走 ReAct。"""

    def __init__(self):
        self.mock = is_mock_mode()
        self.tool = python_repl
        if not self.mock:
            llm = ChatOpenAI(
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                temperature=0,
            )
            self.agent = create_agent(llm, [self.tool], name="coder")

    def invoke(self, state):
        if self.mock:
            # mock 模式下用简单代码示例验证工具链路
            code = "print(12345 * 6789)"
            return run_tool_and_reply(self.tool, {"code": code})
        return self.agent.invoke(state)


def build_coder():
    """构建 Coder 智能体节点。"""
    return CoderAgent()
