"""Supervisor —— 主管路由智能体

职责：接收用户输入，用 LLM 判断任务类型，路由到合适的 Worker。
路由逻辑：
    - web_search  → Researcher（搜索）
    - python      → Coder（代码执行）
    - sql         → DBAgent（数据库查询）
    - rag         → RAGAgent（知识库问答）
    - FINISH      → 直接结束（简单问题无需 Worker）
"""
import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL

# 可选路由目标
ROUTES = Literal["researcher", "coder", "db_agent", "rag_agent", "FINISH"]

# 路由决策的 System Prompt
SYSTEM_PROMPT = """你是一个任务路由器。根据用户的问题，判断应该交给哪个专业智能体处理。

可选路由：
- researcher: 需要实时信息、新闻、资料、事实核查的搜索类问题
- coder: 需要数学计算、代码执行、数据分析、脚本编写的问题
- db_agent: 需要查询或操作数据库（SQL）的问题
- rag_agent: 需要查询业务知识库、业务规则、内部文档、历史数据记录的问题（知识库问答）
- FINISH: 简单问候、闲聊、或无需任何工具即可直接回答的问题

只输出一个 JSON 对象，格式：{"route": "路由名"}
不要输出任何其他内容。
"""


# mock 路由用的关键词规则（当 API key 为占位符时启用）
# (关键词, 路由)
_MOCK_RULES = [
    (["搜索", "查一下", "查询信息", "查找", "新闻", "资料", "实时", "搜索一下"], "researcher"),
    (["计算", "等于多少", "运行代码", "执行", "python", "脚本", "数据分析", "算一下"], "coder"),
    (["数据库", "sql", "查询表", "users表", "select", "insert", "update", "delete"], "db_agent"),
    (["业务规则", "知识库", "订单规则", "状态说明", "支付类型", "平台说明", "内部文档", "业务说明"], "rag_agent"),
]


def _mock_route(text: str) -> str:
    """基于关键词的简单路由，用于 API key 为占位符时验证架构。"""
    text_lower = text.lower()
    for keywords, route in _MOCK_RULES:
        if any(k.lower() in text_lower for k in keywords):
            return route
    return "FINISH"


class Supervisor:
    """主管路由智能体：接收消息，返回路由决策。"""

    def __init__(self):
        self.use_mock = not OPENAI_API_KEY or OPENAI_API_KEY == "sk-占位符"
        self.llm = ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0,
        )

    def route(self, messages) -> str:
        """根据消息内容决定路由目标。"""
        # 取最后一条用户消息
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.type == "human":
                last_user_msg = msg.content
                break

        # mock 模式：用关键词规则路由
        if self.use_mock:
            route = _mock_route(last_user_msg)
            print(f"[Supervisor] mock 模式（未配置真实 API key）")
            return route

        try:
            resp = self.llm.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=f"用户问题: {last_user_msg}"),
                ]
            )
            route = json.loads(resp.content)["route"]
            if route not in ("researcher", "coder", "db_agent", "rag_agent", "FINISH"):
                return "FINISH"
            return route
        except Exception as e:
            # 解析失败时保守地直接结束，避免路由错误
            print(f"[Supervisor] 路由解析失败，回退到 FINISH: {e}")
            return "FINISH"


supervisor = Supervisor()


def supervisor_node(state) -> dict:
    """LangGraph 节点：调用 supervisor 路由，返回下一步去向。"""
    route = supervisor.route(state["messages"])
    print(f"[Supervisor] 路由决策 → {route}")
    return {"route": route}


def route_after_supervisor(state) -> ROUTES:
    """条件边：根据 state 里的 route 决定下一个节点。"""
    return state["route"]
