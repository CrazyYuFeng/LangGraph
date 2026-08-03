"""rag/reranker.py —— Rerank 重排序

用交叉编码器（cross-encoder）对检索结果精排，提升精度。
模型：cross-encoder/ms-marco-MiniLM-L-6-v2（约 80MB）
模型已手动下载到 rag/models/ms-marco-MiniLM-L-6-v2/（避免网络问题）
"""
import os
from typing import List

from langchain_core.documents import Document

# 本地模型目录（手动下载放置）
RERANK_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "ms-marco-MiniLM-L-6-v2")

# 延迟导入，避免首次加载过慢
_reranker = None


def _get_reranker():
    """懒加载 reranker 模型（从本地目录加载，不联网）。"""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        # 从本地目录加载模型，避免网络下载
        _reranker = CrossEncoder(RERANK_MODEL_DIR)
    return _reranker


def rerank(query: str, docs: List[Document], top_k: int = None) -> List[Document]:
    """对检索结果进行 Rerank 精排。

    Args:
        query: 查询文本
        docs: 待重排的文档列表
        top_k: 保留前几条（默认全部）

    Returns:
        重排后的文档列表（按相关性降序）
    """
    if not docs:
        return []

    model = _get_reranker()

    # 构造 (query, document) 对
    pairs = [(query, d.page_content) for d in docs]

    # 计算相关度分数
    scores = model.predict(pairs)

    # 按分数降序排序
    scored = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)

    # 确定保留数量
    limit = top_k if top_k is not None else len(scored)
    selected = scored[:limit]

    # 记录 rerank 分数
    result = []
    for idx, (doc, score) in enumerate(selected):
        doc.metadata["rerank_score"] = float(score)
        doc.metadata["rerank_rank"] = idx
        result.append(doc)

    return result
