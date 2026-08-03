"""rag/tracing.py —— Langfuse 可观测性封装

记录每次 RAG 查询的 trace：检索到的 chunk、rerank 分数、LLM 输入输出。
用于定位缺陷（召回失败/污染/幻觉）和审计。

设计：可选启用。
    - 未配置 LANGFUSE_PUBLIC_KEY/SECRET_KEY 时，get_tracing() 返回 None，
      所有调用静默跳过，不影响正常功能。
    - 配置后自动启用，无需改业务代码。

用法：
    from rag.tracing import get_tracing
    tracing = get_tracing()
    if tracing:
        with tracing.start_trace("rag_query", query=question) as trace:
            trace.log_retrieval(docs)
            trace.log_generation(query, context, answer)
"""
from typing import List, Optional

from langchain_core.documents import Document

from rag.config import (
    LANGFUSE_ENABLED,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)
from rag.logging_setup import get_logger

logger = get_logger(__name__)


class _NullTrace:
    """空实现：未启用 Langfuse 时使用，所有方法静默跳过。"""

    def log_retrieval(self, *args, **kwargs):
        pass

    def log_generation(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _LangfuseTrace:
    """Langfuse trace 封装：记录一次 RAG 查询的完整链路。"""

    def __init__(self, langfuse_client, trace_name: str, **trace_kwargs):
        self._client = langfuse_client
        self._trace_name = trace_name
        self._client_kwargs = trace_kwargs

    def _start_observation(self, name: str, as_type: str, input=None):
        """创建观测对象（兼容新旧 API）。"""
        try:
            # 新版 API（langfuse 4.x）：start_observation
            obs = self._client.start_observation(
                name=name, as_type=as_type, input=input
            )
        except AttributeError:
            # 旧版 API：client.trace().span()
            trace = self._client.trace(name=self._trace_name, **self._client_kwargs)
            obs = trace.span(name=name, input=input)
        return obs

    def log_retrieval(
        self,
        docs: List[Document],
        query: Optional[str] = None,
        stage: str = "retrieval",
    ):
        """记录检索结果（chunk 内容 + 分数）。"""
        payload = {
            "query": query,
            "num_docs": len(docs),
            "docs": [
                {
                    "id": d.id,
                    "content": d.page_content[:500],  # 截断避免 trace 过大
                    "source": d.metadata.get("source"),
                    "score": d.metadata.get("score"),
                    "vector_score": d.metadata.get("vector_score"),
                    "rerank_score": d.metadata.get("rerank_score"),
                }
                for d in docs
            ],
        }
        obs = self._start_observation(name=stage, as_type="retriever", input=payload)
        obs.update(output={"num_docs": len(docs)})
        obs.end()

    def log_generation(
        self,
        query: str,
        context: str,
        answer: str,
        stage: str = "generation",
    ):
        """记录 LLM 生成（输入上下文 + 输出答案）。"""
        obs = self._start_observation(
            name=stage,
            as_type="generation",
            input={"query": query, "context": context[:2000]},
        )
        obs.update(output={"answer": answer})
        obs.end()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            self._client.flush()
        except Exception:
            pass
        return False


# 单例
_client = None


def _get_client():
    """懒加载 Langfuse 客户端。"""
    global _client
    if _client is None and LANGFUSE_ENABLED:
        try:
            from langfuse import Langfuse

            _client = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST,
            )
            # 验证连接（key 无效会抛异常）
            _client.auth_check()
            logger.info("Langfuse 已启用")
        except Exception as e:
            logger.error("Langfuse 初始化失败（trace 将禁用）: %s", e)
            _client = None
    return _client


def get_tracing():
    """获取 trace 上下文管理器。

    未启用时返回 _NullTrace（静默跳过），启用时返回 _LangfuseTrace。
    """
    client = _get_client()
    if client is None:
        return _NullTrace()
    return _LangfuseTrace(client, "rag_query")


def is_tracing_enabled() -> bool:
    """是否已启用 Langfuse trace。"""
    return _get_client() is not None
