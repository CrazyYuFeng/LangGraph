"""rag/main.py —— RAG 系统入口

用法:
    ../bin/python main.py --ingest          # 构建索引（首次运行）
    ../bin/python main.py "你的问题"         # 问答
    ../bin/python main.py "问题" --show-source  # 问答并显示引用来源
"""
import argparse
import sys

from rag.ingest import build_index
from rag.rag_chain import get_rag_chain


def main():
    parser = argparse.ArgumentParser(description="RAG 业务数据问答")
    parser.add_argument("question", nargs="*", help="要问的问题")
    parser.add_argument("--ingest", action="store_true", help="构建索引")
    parser.add_argument("--rebuild", action="store_true", help="重建索引")
    parser.add_argument("--show-source", action="store_true", help="显示引用来源")
    args = parser.parse_args()

    # 构建索引
    if args.ingest or args.rebuild:
        build_index(rebuild=args.rebuild)
        if not args.question:
            return

    question = " ".join(args.question)
    if not question:
        print("用法: python main.py --ingest 或 python main.py \"问题\"")
        return

    # 问答
    chain = get_rag_chain()
    result = chain.answer(question)

    print("\n" + "=" * 50)
    print("回答：")
    print("=" * 50)
    print(result["answer"])

    # 显示引用来源
    if args.show_source and result["sources"]:
        print("\n" + "=" * 50)
        print("引用来源：")
        print("=" * 50)
        for i, doc in enumerate(result["sources"], 1):
            score = doc.metadata.get("score", 0)
            src = doc.metadata.get("source", "?")
            # 来源标识：数据库记录显示订单ID，文件显示文件名
            if src == "db":
                source_label = f"数据库记录 (订单ID:{doc.metadata.get('order_id','')})"
            elif src == "file":
                source_label = f"文件: {doc.metadata.get('file','')}"
            else:
                source_label = src
            print(f"\n[{i}] {source_label}")
            print(f"    相似度: {score:.3f}")
            print(f"    内容: {doc.page_content}")


if __name__ == "__main__":
    main()
