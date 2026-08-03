"""graph.py —— 组装整个混合智能体图

架构：Supervisor → 条件路由 → 各 Worker → 汇总 → END
"""
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Annotated
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
from supervisor import supervisor_node, route_after_supervisor
from workers.researcher import build_researcher
from workers.coder import build_coder
from workers.db_agent import build_db_agent
from workers.rag_agent import build_rag_agent
from tools.wecom_notifier import send_markdown


# ============================================================
# 状态定义
# ============================================================
class AgentState(TypedDict):
    """全局状态：累积所有消息 + 路由决策。"""
    messages: Annotated[list, add_messages]
    route: Literal["researcher", "coder", "db_agent", "rag_agent", "FINISH"]


# ============================================================
# 节点定义
# ============================================================
researcher = build_researcher()
coder = build_coder()
db_agent = build_db_agent()
rag_agent = build_rag_agent()


def researcher_node(state: AgentState) -> dict:
    """调用 Researcher 智能体。"""
    result = researcher.invoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


def coder_node(state: AgentState) -> dict:
    """调用 Coder 智能体。"""
    result = coder.invoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


# 用户要求发企微通知的意图关键词
_NOTIFY_KEYWORDS = ["通知", "发群里", "发企微", "推送到群", "发到群里", "推送", "发消息", "告知大家"]


def _user_wants_notify(state: AgentState) -> bool:
    """判断用户是否要求发企微通知。"""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            text = msg.content.lower()
            return any(k in text for k in _NOTIFY_KEYWORDS)
    return False


def rag_agent_node(state: AgentState) -> dict:
    """调用 RAGAgent 智能体（知识库问答）。"""
    result = rag_agent.invoke(state)
    return {"messages": result["messages"]}


def db_agent_node(state: AgentState) -> dict:
    """调用 DBAgent 智能体，若用户要求则发企微通知。"""
    result = db_agent.invoke({"messages": state["messages"]})

    # 若用户要求发企微通知，则发送 db_agent 的最终回复
    if _user_wants_notify(state):
        last_ai = None
        for msg in reversed(result["messages"]):
            if msg.type == "ai":
                last_ai = msg.content
                break
        if last_ai:
            md = (
                f"## 📊 数据库查询结果\n"
                f"> 用户查询：{state['messages'][-1].content}\n\n"
                f"---\n{last_ai}"
            )
            send_markdown(md)

    return {"messages": result["messages"]}


def finish_node(state: AgentState) -> dict:
    """结束节点：若 Supervisor 直接路由到 FINISH，用 LLM 直接回答简单问题。"""
    # 若最后一条消息已经是 AI 回复（Worker 已处理），则无需再回复
    if state["messages"] and state["messages"][-1].type == "ai":
        return {"messages": []}

    # 否则用 LLM 直接回答简单问题（问候、闲聊等）
    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0.7,
    )
    last_user_msg = state["messages"][-1].content if state["messages"] else ""
    resp = llm.invoke(
        [
            SystemMessage(content="你是一个友好、简洁的助手，直接回答用户的问题，不要使用任何工具。"),
            HumanMessage(content=last_user_msg),
        ]
    )
    return {"messages": [AIMessage(content=resp.content)]}


# ============================================================
# 构建图
# ============================================================
def build_graph():
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("coder", coder_node)
    graph.add_node("db_agent", db_agent_node)
    graph.add_node("rag_agent", rag_agent_node)
    graph.add_node("finish", finish_node)

    # START → supervisor
    graph.add_edge(START, "supervisor")

    # supervisor → 条件路由
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "researcher": "researcher",
            "coder": "coder",
            "db_agent": "db_agent",
            "rag_agent": "rag_agent",
            "FINISH": "finish",
        },
    )

    # 各 Worker → finish → END
    graph.add_edge("researcher", "finish")
    graph.add_edge("coder", "finish")
    graph.add_edge("db_agent", "finish")
    graph.add_edge("rag_agent", "finish")
    graph.add_edge("finish", END)

    return graph.compile()


if __name__ == "__main__":
    # 简单自测
    graph = build_graph()
    print("图构建成功！")
