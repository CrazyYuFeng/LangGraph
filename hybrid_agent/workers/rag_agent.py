"""RAGAgent Worker —— 知识库问答智能体

职责：基于 RAG 检索业务知识库（本地文件 + 数据库记录），回答业务规则、数据查询等问题。
实现：复用 rag/rag_chain.py 的 RAGChain。
"""
import sys
import os

# 确保能导入 rag 包（rag 在项目根目录）
# rag_agent.py 位于 hybrid_agent/workers/ 下，向上三级到项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from langchain_core.messages import AIMessage
from rag.rag_chain import RAGChain


class RAGAgent:
    """RAG 知识库问答智能体。"""

    def __init__(self):
        self.chain = RAGChain()

    def invoke(self, state) -> dict:
        """接收消息，用 RAG 回答，返回 AI 消息。"""
        # 取最后一条用户消息
        query = ""
        for msg in reversed(state["messages"]):
            if msg.type == "human":
                query = msg.content
                break

        # RAG 回答
        result = self.chain.answer(query)

        # 构造 AI 回复（包含答案 + 引用来源）
        answer = result["answer"]
        if result["sources"]:
            answer += "\n\n引用来源："
            for i, doc in enumerate(result["sources"], 1):
                src = doc.metadata.get("source", "?")
                if src == "db":
                    label = f"[{i}] 数据库记录(订单:{doc.metadata.get('order_id','')})"
                else:
                    label = f"[{i}] 文件:{doc.metadata.get('file','')}"
                answer += f"\n{label}"

        return {"messages": [AIMessage(content=answer)]}


def build_rag_agent():
    """构建 RAGAgent 智能体节点。"""
    return RAGAgent()
