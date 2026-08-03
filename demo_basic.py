"""LangGraph 基础 Demo —— 最简单的 StateGraph 示例
运行方式：
    ./bin/python demo_basic.py
"""
from langgraph.graph import StateGraph, MessagesState, START, END


def mock_llm(state: MessagesState):
    """模拟一个 LLM 节点：接收消息状态，返回 AI 回复"""
    return {"messages": [{"role": "ai", "content": "hello world"}]}


def build_graph():
    """构建并编译状态图"""
    graph = StateGraph(MessagesState)

    # 添加节点
    graph.add_node(mock_llm)

    # 连接边：START -> mock_llm -> END
    graph.add_edge(START, "mock_llm")
    graph.add_edge("mock_llm", END)

    return graph.compile()


if __name__ == "__main__":
    graph = build_graph()

    # 调用图，传入初始消息
    result = graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})

    print("=== 返回结果 ===")
    for msg in result["messages"]:
        print(f"[{msg.type}] {msg.content}")
