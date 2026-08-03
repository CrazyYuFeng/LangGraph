"""DBAgent Worker —— 数据库查询智能体

职责：通过 SQL 查询数据库，处理结构化数据检索、增删改操作。
实现：基于 langchain.agents 的 create_agent，内部 ReAct 循环。
"""
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
from sql.structured_query import STRUCTURED_QUERY_TOOLS, STRUCTURED_QUERY_PROMPT
from mock_helpers import is_mock_mode, run_tool_and_reply

# DBAgent 的系统提示词（结构化查询，LLM 只填参数不写 SQL）
DB_AGENT_PROMPT = f"""你是一个专业的数据库查询智能体。

职责：
- 理解用户的自然语言查询意图，提取查询条件参数
- 使用 query_order_stats 工具查询数据库（该工具接收结构化 JSON 参数）
- 将查询结果整理成清晰、易读的回复

查询参数提取规则：
{STRUCTURED_QUERY_PROMPT}

注意：
- 你只负责提取参数并调用工具，不要直接写 SQL
- 当用户要求"发到群里通知""推送通知""发企微"等时，查询结果会自动通过企业微信发送到群里，你无需担心推送，只需给出清晰的统计结果即可。
- 始终基于查询到的真实数据回答，不要编造。
"""


class DBAgent:
    """DBAgent 智能体：mock 模式下直接执行 SQL，真实模式走 ReAct。"""

    def __init__(self):
        self.mock = is_mock_mode()
        self.tool = STRUCTURED_QUERY_TOOLS[0]
        if not self.mock:
            llm = ChatOpenAI(
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                temperature=0,
            )
            self.agent = create_agent(
                llm,
                STRUCTURED_QUERY_TOOLS,
                name="db_agent",
                system_prompt=DB_AGENT_PROMPT,
            )

    def invoke(self, state):
        if self.mock:
            # mock 模式下用示例参数验证工具链路
            return run_tool_and_reply(self.tool, {"query_json": '{"min_credit": 15}'})
        return self.agent.invoke(state)


def build_db_agent():
    """构建 DBAgent 智能体节点。"""
    return DBAgent()
