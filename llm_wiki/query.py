"""llm_wiki/query.py —— 基于编译产物的问答

简单检索：按问题关键词对 wiki 页面打分，选 top-k 页面作为上下文，
LLM 基于页面回答并标注来源（禁编造）。

用法：
    from llm_wiki.query import query
    result = query("高价值订单怎么统计？")
"""
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from llm_wiki.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    WIKI_DIR,
)

ANSWER_SYSTEM_PROMPT = """你是一个知识库问答助手。回答规则：
1. 只能基于提供的 wiki 页面回答，禁止编造
2. 引用时在引用处标注来源编号，如 [1][2]
3. 页面中没有答案时，明确说"知识库中未找到相关信息"
"""


def _load_pages():
    """读取 wiki 下所有页面（跳过 index.md），剥离 front-matter。"""
    pages = []
    if not WIKI_DIR.is_dir():
        return pages
    for md in sorted(WIKI_DIR.rglob("*.md")):
        if md.name == "index.md":
            continue
        text = md.read_text(encoding="utf-8")
        body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
        pages.append({"file": str(md.relative_to(WIKI_DIR)).replace("\\", "/"), "text": body})
    return pages


def _score(query: str, pages: list) -> list:
    """按查询词在页面中的出现次数打分排序（轻量检索）。"""
    words = [w for w in re.split(r"\W+", query) if w]
    scored = []
    for p in pages:
        cnt = sum(p["text"].count(w) for w in words)
        scored.append((cnt, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored]


def query(question: str, top_k: int = 5) -> dict:
    """基于 wiki 页面回答问题。返回 {"answer", "sources"}。"""
    pages = _load_pages()
    if not pages:
        return {
            "answer": "wiki 为空，请先运行：./bin/python -m llm_wiki.main ingest",
            "sources": [],
        }

    ranked = _score(question, pages)[:top_k]
    context = "\n\n".join(
        f"[{i + 1}]\n{p['text']}" for i, p in enumerate(ranked)
    )

    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0,
    )
    resp = llm.invoke(
        [
            SystemMessage(content=ANSWER_SYSTEM_PROMPT),
            HumanMessage(content=f"问题：{question}\n\n可用资料：\n{context}"),
        ]
    )
    return {"answer": resp.content, "sources": [p["file"] for p in ranked]}
