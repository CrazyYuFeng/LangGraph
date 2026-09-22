"""llm_wiki/main.py —— CLI 入口

用法（项目根目录下）：
    ./bin/python -m llm_wiki.main ingest [--rebuild]   摄入 rag/knowledge/*.md
    ./bin/python -m llm_wiki.main list                 列出已编译页面
    ./bin/python -m llm_wiki.main query "你的问题"      基于 wiki 问答
"""
import argparse

from llm_wiki.ingest import ingest, load_manifest
from llm_wiki.query import query


def main():
    parser = argparse.ArgumentParser(
        description="LLM Wiki：把 rag/knowledge/*.md 编译成互链知识库"
    )
    sub = parser.add_subparsers(dest="cmd")

    p_ingest = sub.add_parser("ingest", help="摄入知识库（增量，--rebuild 全量重编）")
    p_ingest.add_argument("--rebuild", action="store_true", help="忽略 manifest 全量重编")

    sub.add_parser("list", help="列出 wiki 页面")

    p_query = sub.add_parser("query", help="基于 wiki 问答")
    p_query.add_argument("question", nargs="+", help="问题内容")

    args = parser.parse_args()

    if args.cmd == "ingest":
        r = ingest(rebuild=args.rebuild)
        print(f"编译 {r['compiled']} 个文件，跳过 {r['skipped']} 个未变更文件")
        for f in r["failed"]:
            print(f"  [失败] {f['file']}: {f['error']}")
    elif args.cmd == "list":
        manifest = load_manifest()
        if not manifest:
            print("wiki 为空，请先运行：./bin/python -m llm_wiki.main ingest")
        for src, info in manifest.items():
            print(f"\n{src}（{len(info['pages'])} 页，编译于 {info['compiled_at']}）")
            for pf in info["pages"]:
                print(f"  - {pf}")
    elif args.cmd == "query":
        q = " ".join(args.question)
        r = query(q)
        print("\n回答：\n" + r["answer"])
        if r["sources"]:
            print("\n来源页面：")
            for s in r["sources"]:
                print(f"  - {s}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
