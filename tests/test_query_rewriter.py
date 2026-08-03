"""tests/test_query_rewriter.py —— 查询改写模块测试

覆盖不依赖真实 LLM 的纯逻辑：
    - _parse_queries：解析 LLM 返回的各种格式
    - multi_query 的容错解析（通过 mock LLM 返回模拟数据）
"""
import sys
from pathlib import Path
from unittest.mock import patch

# 确保能导入 rag 包（项目根目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from rag.query_rewriter import _parse_queries, multi_query


# ============================================================
# _parse_queries（解析逻辑）
# ============================================================
class TestParseQueries:
    def test_standard_json(self):
        assert _parse_queries('["a", "b", "c"]') == ["a", "b", "c"]

    def test_markdown_json_block(self):
        """应能剥离 markdown 代码块。"""
        text = '```json\n["a", "b"]\n```'
        assert _parse_queries(text) == ["a", "b"]

    def test_non_json_fallback(self):
        """非 JSON 时退化按行/逗号切分。"""
        assert _parse_queries("a\nb\nc") == ["a", "b", "c"]
        assert _parse_queries("a, b, c") == ["a", "b", "c"]

    def test_empty_result(self):
        assert _parse_queries("") == []

    def test_filters_non_string(self):
        """应过滤非字符串元素。"""
        assert _parse_queries('["a", 123, null, "b"]') == ["a", "b"]


# ============================================================
# multi_query（通过 mock LLM）
# ============================================================
class TestMultiQuery:
    def _mock_llm(self, content: str):
        """构造返回指定文本的 mock LLM。"""
        mock = type("MockLLM", (), {})()
        resp = type("MockResp", (), {"content": content})()
        mock.invoke = lambda prompt: resp
        return mock

    def test_includes_original_question(self):
        """多查询结果应始终包含原问题。"""
        with patch("rag.query_rewriter._get_llm", return_value=self._mock_llm('["变体1", "变体2"]')):
            result = multi_query("原始问题", num=2)
        assert result[0] == "原始问题"

    def test_deduplicates(self):
        """重复的查询应去重。"""
        with patch("rag.query_rewriter._get_llm", return_value=self._mock_llm('["变体1", "变体1", "变体2"]')):
            result = multi_query("原始问题", num=3)
        assert result.count("变体1") == 1

    def test_respects_num_limit(self):
        """结果数量应受 num 限制（含原问题）。"""
        with patch("rag.query_rewriter._get_llm", return_value=self._mock_llm('["a", "b", "c", "d"]')):
            result = multi_query("原始问题", num=3)
        # 原问题 + 最多 3 个变体
        assert len(result) <= 4

    def test_handles_markdown_response(self):
        """应能处理 markdown 代码块包裹的返回。"""
        with patch("rag.query_rewriter._get_llm", return_value=self._mock_llm('```json\n["a", "b"]\n```')):
            result = multi_query("原始问题", num=2)
        assert "a" in result
        assert "b" in result
