"""tests/test_retrieval.py —— 检索模块测试

覆盖不依赖真实向量库/数据库的纯逻辑：
    - _tokenize：中文分词
    - HybridRetriever._rrf_fuse：RRF 融合排序
    - 阈值过滤逻辑（构造带 vector_score 的文档验证）
"""
import sys
from pathlib import Path

# 确保能导入 rag 包（项目根目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest
from langchain_core.documents import Document

from rag.hybrid_retriever import HybridRetriever, _tokenize


def _make_doc(content: str, doc_id: str) -> Document:
    """构造测试用 Document。"""
    doc = Document(page_content=content, metadata={})
    doc.id = doc_id
    return doc


# ============================================================
# _tokenize（中文分词）
# ============================================================
class TestTokenize:
    def test_chinese_tokenizes(self):
        tokens = _tokenize("订单金额查询")
        assert len(tokens) > 0
        assert "订单" in tokens or "金额" in tokens

    def test_returns_list(self):
        assert isinstance(_tokenize("测试"), list)


# ============================================================
# _rrf_fuse（RRF 融合）
# ============================================================
class TestRRFFuse:
    def test_empty_inputs(self):
        assert HybridRetriever._rrf_fuse([], []) == []

    def test_merges_both_sources(self):
        """两个来源的文档应合并，去重。"""
        v1 = _make_doc("向量文档1", "v1")
        v2 = _make_doc("向量文档2", "v2")
        b1 = _make_doc("bm25文档1", "b1")
        fused = HybridRetriever._rrf_fuse([v1, v2], [b1])
        ids = [d.id for d in fused]
        assert set(ids) == {"v1", "v2", "b1"}

    def test_deduplicates_same_doc(self):
        """同一文档出现在两个来源时应只保留一次。"""
        doc = _make_doc("同一文档", "same")
        fused = HybridRetriever._rrf_fuse([doc], [doc])
        assert len(fused) == 1
        assert fused[0].id == "same"

    def test_ranks_by_rrf_score(self):
        """RRF 分数应正确计算并排序。"""
        # 向量检索第1位 + BM25第1位 → 分数最高
        top = _make_doc("top文档", "top")
        # 只在向量检索第5位，BM25没出现 → 分数较低
        low = _make_doc("low文档", "low")
        fused = HybridRetriever._rrf_fuse(
            [top, _make_doc("x", "x"), _make_doc("y", "y"), _make_doc("z", "z"), low],
            [top],
        )
        assert fused[0].id == "top"
        assert fused[0].metadata["rrf_score"] > 0

    def test_sets_rrf_score_metadata(self):
        doc = _make_doc("文档", "d1")
        fused = HybridRetriever._rrf_fuse([doc], [])
        assert "rrf_score" in fused[0].metadata
        assert fused[0].metadata["rrf_score"] > 0


# ============================================================
# 阈值过滤逻辑（模拟 retriever.py 的过滤行为）
# ============================================================
class TestThresholdFilter:
    def test_filters_below_threshold(self):
        """低于阈值的文档应被过滤。"""
        threshold = 0.4
        docs = [
            _make_doc("高分", "h1"),
            _make_doc("低分", "l1"),
        ]
        docs[0].metadata["vector_score"] = 0.8
        docs[1].metadata["vector_score"] = 0.2

        filtered = [
            d for d in docs if d.metadata.get("vector_score", 0) >= threshold
        ]
        assert len(filtered) == 1
        assert filtered[0].id == "h1"

    def test_keeps_at_threshold(self):
        """等于阈值的文档应保留。"""
        threshold = 0.4
        doc = _make_doc("临界", "c1")
        doc.metadata["vector_score"] = 0.4
        filtered = [d for d in [doc] if d.metadata.get("vector_score", 0) >= threshold]
        assert len(filtered) == 1

    def test_missing_score_treated_as_zero(self):
        """无 vector_score 的文档按 0 处理，应被过滤。"""
        threshold = 0.4
        doc = _make_doc("无分数", "n1")
        filtered = [d for d in [doc] if d.metadata.get("vector_score", 0) >= threshold]
        assert len(filtered) == 0
