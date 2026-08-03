"""main.py —— 混合智能体入口

用法:
    ../bin/python main.py "你的问题"

示例:
    ../bin/python main.py "帮我查一下 2024 年诺贝尔物理学奖得主"
    ../bin/python main.py "计算 12345 * 6789 等于多少"
    ../bin/python main.py "你好"
"""
import sys

from graph import build_graph


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py \"你的问题\"")
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    print(f"\n[用户] {question}\n")

    graph = build_graph()
    result = graph.invoke({"messages": [{"role": "user", "content": question}]})

    print("\n" + "=" * 50)
    print("最终回复：")
    print("=" * 50)
    # 打印最后一条 AI 消息
    for msg in result["messages"]:
        if msg.type == "ai":
            print(f"\n{msg.content}")


if __name__ == "__main__":
    main()
