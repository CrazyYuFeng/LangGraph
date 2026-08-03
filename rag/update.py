"""rag/update.py —— 定时增量更新入口

用法：
    ../bin/python -m rag.update            # 增量更新
    ../bin/python -m rag.update --rebuild  # 全量重建

配合 cron 定时执行，实现企业级 RAG 持续更新。
"""
import argparse

from rag.ingest import build_index, incremental_update
from rag.cache import query_cache
from rag.logging_setup import get_logger

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="RAG 索引更新")
    parser.add_argument("--rebuild", action="store_true", help="全量重建索引")
    args = parser.parse_args()

    if args.rebuild:
        logger.info("=== 全量重建索引 ===")
        build_index(rebuild=True)
    else:
        logger.info("=== 增量更新索引 ===")
        incremental_update()

    # 更新索引后清空缓存，避免返回旧数据
    query_cache.clear()


if __name__ == "__main__":
    main()
