"""rag/hybrid_retriever.py —— 混合检索（向量 + BM25 关键词）

提升召回率：向量检索捕捉语义相似，BM25 捕捉关键词精确匹配，两者互补。
融合方式：RRF（Reciprocal Rank Fusion）加权融合两个检索结果。
"""
import os
from typing import List, Optional

from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
import jieba

from rag.config import TOP_K
from rag.vectorstore import get_vectorstore


def _tokenize(text: str) -> List[str]:
    """中文分词（用 jieba），用于 BM25 关键词检索。"""
    return list(jieba.cut(text))


class HybridRetriever:
    """混合检索器：向量检索 + BM25 关键词检索，RRF 融合。"""

    def __init__(self):
        # 使用统一向量库接口（支持 chroma/pgvector/milvus 切换）
        self.vectorstore = get_vectorstore()
        # 加载所有文档用于 BM25
        self._all_docs = self._load_all_docs()
        self._bm25 = self._build_bm25(self._all_docs)

    def _load_all_docs(self) -> List[Document]:
        """从向量库加载所有文档（用于 BM25 建立关键词索引）。"""
        data = self.vectorstore.get(include=["documents", "metadatas"])
        docs = []
        ids = data.get("ids", [])
        contents = data.get("documents", [])
        metadatas = data.get("metadatas", [])
        for i, content in enumerate(contents):
            doc = Document(page_content=content, metadata=metadatas[i] if i < len(metadatas) else {})
            doc.id = ids[i] if i < len(ids) else None
            docs.append(doc)
        return docs

    def _build_bm25(self, docs: List[Document]):
        """基于文档内容构建 BM25 索引。"""
        tokenized = [_tokenize(d.page_content) for d in docs]
        return BM25Okapi(tokenized)

    def _bm25_search(self, query: str, k: int) -> List[Document]:
        """BM25 关键词检索。"""
        query_tokens = _tokenize(query)
        scores = self._bm25.get_scores(query_tokens)
        # 取 top-k
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for i in top_indices:
            if scores[i] > 0:
                doc = self._all_docs[i]
                doc.metadata["bm25_score"] = scores[i]
                results.append(doc)
        return results

    def _vector_search(self, query: str, k: int, filter_meta: Optional[dict]) -> List[Document]:
        """向量检索。"""
        results = self.vectorstore.similarity_search_with_relevance_scores(
            query, k=k, filter=filter_meta
        )
        docs = []
        for doc, score in results:
            doc.metadata["vector_score"] = score
            docs.append(doc)
        return docs

    @staticmethod
    def _rrf_fuse(vector_docs: List[Document], bm25_docs: List[Document], k: int = 60) -> List[Document]:
        """RRF 融合两个检索结果。"""
        # 计算每个文档的 RRF 分数
        rrf_scores = {}
        doc_map = {}

        for rank, doc in enumerate(vector_docs):
            doc_id = doc.id or doc.page_content
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
            doc_map[doc_id] = doc
        for rank, doc in enumerate(bm25_docs):
            doc_id = doc.id or doc.page_content
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
            doc_map[doc_id] = doc

        # 按 RRF 分数排序
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
        fused = [doc_map[i] for i in sorted_ids]
        for doc in fused:
            doc.metadata["rrf_score"] = rrf_scores[doc.id or doc.page_content]
        return fused

    def retrieve(
        self,
        query: str,
        k: int = TOP_K,
        filter_meta: Optional[dict] = None,
    ) -> List[Document]:
        """混合检索：向量 + BM25，RRF 融合。"""
        # 向量检索（召回多一点，便于融合）
        vector_docs = self._vector_search(query, k=k * 2, filter_meta=filter_meta)
        # BM25 检索
        bm25_docs = self._bm25_search(query, k=k * 2)

        # RRF 融合
        fused = self._rrf_fuse(vector_docs, bm25_docs)

        return fused[:k]


def get_hybrid_retriever() -> HybridRetriever:
    """获取混合检索器单例。"""
    return HybridRetriever()
