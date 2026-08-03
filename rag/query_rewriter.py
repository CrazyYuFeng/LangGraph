"""rag/query_rewriter.py —— 查询改写 / 多查询扩展

解决召回率低的问题（用户口语化提问、问法不同但意思相同）。

两个能力：
    1. query_rewrite：LLM 把口语化问题改写成规范检索查询（1 条）
    2. multi_query：LLM 把一个问题改写成多个角度，分别检索再合并去重

设计说明：
    - 默认不强制启用（每次改写都增加一次 LLM 调用延迟）。
    - 通过 RAGRetriever 的 rewrite / multi_query 参数按需开启。
"""
import json
import re
from typing import List, Optional

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from rag.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


# ============================================================
# LLM 实例（懒加载）
# ============================================================
_rewriter_llm = None


def _get_llm() -> ChatOpenAI:
    """懒加载改写用 LLM（复用项目 DeepSeek 配置）。"""
    global _rewriter_llm
    if _rewriter_llm is None:
        _rewriter_llm = ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0,  # 改写要稳定，不发散
        )
    return _rewriter_llm


# ============================================================
# 查询改写（Query Rewriting）
# ============================================================
_REWRITE_PROMPT = """你是一个检索查询改写助手。用户会给出一个口语化/模糊的问题，
请把它改写成一条适合向量检索和关键词检索的规范查询。

要求：
- 保留所有关键信息（金额、时间、用户、订单、状态、平台等）
- 补充必要的业务术语（如把"多少钱"改写为"金额 CREDIT"）
- 去除口语、指代（"它""那个"等），明确化
- 只输出改写后的查询，不要解释，不要加引号

用户问题：{question}
改写后的查询："""


def query_rewrite(question: str) -> str:
    """把口语化问题改写成规范检索查询。"""
    prompt = _REWRITE_PROMPT.format(question=question)
    resp = _get_llm().invoke(prompt)
    rewritten = resp.content.strip().strip('"').strip("'")
    return rewritten


# ============================================================
# 多查询（Multi-Query）
# ============================================================
_MULTI_QUERY_PROMPT = """你是一个检索查询扩展助手。用户会给出一个问题，
请从不同角度把它改写成 {num} 条检索查询，以提高召回率。

要求：
- 每条查询覆盖问题的不同侧面（如不同关键词、不同表述、不同维度）
- 每条查询独立、完整、可单独用于检索
- 只输出 JSON 数组，如 ["查询1", "查询2", "查询3"]，不要其他内容

用户问题：{question}
JSON 数组："""


def _parse_queries(text: str) -> List[str]:
    """解析 LLM 返回的查询列表（容错处理）。

    支持格式：
        - 标准 JSON 数组：["a", "b"]
        - markdown 代码块包裹的 JSON：```json [...]```
        - 非 JSON（退化按行/逗号切分）

    Args:
        text: LLM 返回的原始文本

    Returns:
        解析后的查询字符串列表（未去重，保留原始顺序）
    """
    # 剥离 markdown 代码块
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        queries = json.loads(text)
    except json.JSONDecodeError:
        # 退化：按行/逗号切分
        queries = [q.strip().strip('"').strip("'") for q in re.split(r"[\n,]", text) if q.strip()]
    # 只保留字符串类型
    return [q for q in queries if isinstance(q, str) and q.strip()]


def multi_query(question: str, num: int = 3) -> List[str]:
    """把一个问题改写成多个角度的检索查询。"""
    prompt = _MULTI_QUERY_PROMPT.format(question=question, num=num)
    resp = _get_llm().invoke(prompt)
    queries = _parse_queries(resp.content)
    # 去重、去空，保留原问题
    result = [question]
    for q in queries:
        if q.strip() not in result:
            result.append(q.strip())
    return result[:num + 1]


# ============================================================
# 多查询检索（分别检索 + 合并去重）
# ============================================================
def multi_query_retrieve(
    retriever,
    question: str,
    k: int,
    num_queries: int = 3,
    filter_meta: Optional[dict] = None,
) -> List[Document]:
    """多查询检索：改写多个查询，分别检索，合并去重。

    只做候选收集（混合检索），不在此处精排；由外层 RAGRetriever
    统一做一次 Rerank 精排，避免重复精排开销。

    Args:
        retriever: RAGRetriever 实例（用其 hybrid 混合检索器收集候选）
        question: 原始问题
        k: 每个查询的召回数量
        num_queries: 改写查询数量（不含原问题）
        filter_meta: 元数据过滤

    Returns:
        合并去重后的候选文档列表
    """
    queries = multi_query(question, num=num_queries)
    all_docs = []
    seen_ids = set()

    for q in queries:
        # 用混合检索收集候选（召回多一点，供外层精排）
        candidates = retriever.hybrid.retrieve(q, k=k, filter_meta=filter_meta)
        for doc in candidates:
            doc_id = doc.id or doc.page_content
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                all_docs.append(doc)

    return all_docs


if __name__ == "__main__":
    # 简单自测
    q = "上个月花了多少钱"
    print("原始问题:", q)
    print("改写后:", query_rewrite(q))
    print("多查询:", multi_query(q))
