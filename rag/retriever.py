"""rag/retriever.py —— 检索模块（混合检索 + Rerank）

提升召回率和精度：
    1. 混合检索：向量 + BM25 关键词（RRF 融合）—— 提升召回
    2. Rerank：交叉编码器精排 —— 提升精度
    3. 阈值过滤：过滤低分无关文档 —— 控制上下文污染
"""
from typing import List, Optional

from langchain_core.documents import Document

from rag.config import TOP_K, SCORE_THRESHOLD
from rag.hybrid_retriever import get_hybrid_retriever
from rag.reranker import rerank
from rag.query_rewriter import query_rewrite, multi_query_retrieve


class RAGRetriever:
    """RAG 检索器：混合检索 + Rerank + 阈值过滤。"""

    def __init__(self):
        self.hybrid = get_hybrid_retriever()

    def retrieve(
        self,
        query: str,
        k: int = TOP_K,
        score_threshold: float = SCORE_THRESHOLD,
        filter_meta: Optional[dict] = None,
        rewrite: bool = False,
        multi_query: bool = False,
        num_queries: int = 3,
    ) -> List[Document]:
        """检索相关文档，应用 Rerank + 阈值过滤。

        Args:
            query: 查询文本
            k: 召回数量
            score_threshold: 相似度阈值（过滤低分无关文档）
            filter_meta: 元数据过滤条件，如 {"source": "db", "status": "1"}
            rewrite: 是否查询改写（LLM 把口语化问题转成规范查询）
            multi_query: 是否多查询（改写多个角度检索后合并去重）
            num_queries: 多查询时改写查询数量（不含原问题）
        """
        # 0. 查询改写 / 多查询（提升召回率）
        if multi_query:
            # 多查询：改写多个角度，分别收集候选 + 合并去重
            candidates = multi_query_retrieve(
                self, query, k=k * 3, num_queries=num_queries, filter_meta=filter_meta
            )
            # 统一精排 + 阈值过滤（上下文污染控制）
            reranked = rerank(query, candidates, top_k=k)
            filtered = []
            for doc in reranked:
                score = doc.metadata.get("vector_score", 0)
                if score >= score_threshold:
                    doc.metadata["score"] = score
                    filtered.append(doc)
            return filtered

        if rewrite:
            query = query_rewrite(query)

        # 1. 混合检索（召回多一点，供 Rerank 精排）
        candidates = self.hybrid.retrieve(query, k=k * 3, filter_meta=filter_meta)

        # 2. Rerank 精排
        reranked = rerank(query, candidates, top_k=k)

        # 3. 阈值过滤（上下文污染控制）
        filtered = []
        for doc in reranked:
            score = doc.metadata.get("vector_score", 0)
            if score >= score_threshold:
                doc.metadata["score"] = score
                filtered.append(doc)

        return filtered


def get_retriever() -> RAGRetriever:
    """获取检索器单例。"""
    return RAGRetriever()
