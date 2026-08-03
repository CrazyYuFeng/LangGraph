"""rag/rag_chain.py —— RAG 问答链

解决幻觉问题的三层防线：
    1. 检索层：RAGRetriever 阈值过滤（已在 retriever.py）
    2. 生成层：强约束 prompt（只能基于资料回答）
    3. 验证层：要求标注引用来源，并展示检索到的资料供核对
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from rag.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from rag.retriever import RAGRetriever
from rag.cache import query_cache
from rag.tracing import get_tracing


# 强约束 prompt（解决幻觉）
SYSTEM_PROMPT = """你是一个严谨的业务数据问答助手。

回答规则：
1. 只能基于【提供的资料】回答，禁止编造任何信息
2. 如果资料中没有答案，明确说"资料中未找到相关信息"
3. 引用资料时，在引用处标注来源编号，如 [1][2]
4. 在回答末尾，把用到的来源编号和对应的来源名称列出来
5. 不要补充资料之外的知识
6. 涉及金额、数量等数据时，只引用资料中的真实数值，不要计算或推测

提供的资料：
{context}

回答末尾请按此格式列出引用来源：
引用来源：[1] 来源名称1，[2] 来源名称2
"""


class RAGChain:
    """RAG 问答链：检索 + 生成。"""

    def __init__(self):
        self.retriever = RAGRetriever()
        self.llm = ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0,  # 精确回答，不发散
        )

    def answer(
        self,
        query: str,
        k: int = 5,
        filter_meta: dict = None,
        use_cache: bool = True,
        rewrite: bool = False,
        multi_query: bool = False,
        num_queries: int = 3,
    ) -> dict:
        """回答问题，返回答案 + 检索到的资料（引用溯源）。

        Args:
            query: 查询问题
            k: 召回数量
            filter_meta: 元数据过滤
            use_cache: 是否使用缓存（默认 True）
            rewrite: 是否查询改写（LLM 把口语化问题转成规范查询）
            multi_query: 是否多查询（改写多个角度检索后合并去重）
            num_queries: 多查询时改写查询数量（不含原问题）
        """
        # 0. 查缓存（相同问题直接返回）
        if use_cache:
            cached = query_cache.get(query)
            if cached:
                return {"answer": cached, "sources": [], "cached": True}

        # 可观测性：开启 trace（未配置 Langfuse 时静默跳过）
        with get_tracing() as trace:
            # 1. 检索
            docs = self.retriever.retrieve(
                query, k=k, filter_meta=filter_meta,
                rewrite=rewrite, multi_query=multi_query, num_queries=num_queries,
            )
            trace.log_retrieval(docs, query=query)

            # 2. 构建上下文（带编号，便于引用溯源）
            if not docs:
                return {
                    "answer": "资料库中未找到与问题相关的信息。",
                    "sources": [],
                    "cached": False,
                }

            context_parts = []
            for i, doc in enumerate(docs, 1):
                src = doc.metadata.get("source", "?")
                if src == "db":
                    label = f"[{i}] 数据库记录(订单:{doc.metadata.get('order_id','')})"
                else:
                    label = f"[{i}] 文件:{doc.metadata.get('file','')}"
                context_parts.append(f"{label}\n{doc.page_content}")

            context = "\n\n".join(context_parts)

            # 3. 生成
            resp = self.llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT.format(context=context)),
                HumanMessage(content=query),
            ])
            answer = resp.content
            trace.log_generation(query, context, answer)

        # 4. 写入缓存
        if use_cache:
            query_cache.set(query, answer)

        return {
            "answer": answer,
            "sources": docs,  # 返回检索到的资料，供核对
            "cached": False,
        }


def get_rag_chain() -> RAGChain:
    """获取 RAG 问答链单例。"""
    return RAGChain()
