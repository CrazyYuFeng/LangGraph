"""llm_wiki/compiler.py —— LLM 编译引擎

把一个源文档编译成多个结构化 wiki 页面（Karpathy LLM Wiki 模式）：
    - 页面带 front-matter（标题/来源/标签），页面间用 [[双链]] 互链
    - 模型输出严格 JSON（页面数组），此处负责调用与解析容错
"""
import json
import re
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from llm_wiki.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

COMPILE_SYSTEM_PROMPT = """你是一个知识编译引擎。把提供的原始文档编译成结构化、可长期复用的 wiki 页面。

要求：
1. 提炼文档的核心概念，每个概念生成一个独立页面；页面数量以内容为准，不要生硬合并
2. 页面正文用 markdown 编写，保留关键事实、数值、规则、状态码等，不得编造原文没有的信息
3. 页面之间用 [[双链]] 标记关联概念（使用中文双链，如 [[订单状态]]）
4. 只返回一个严格 JSON 对象，不要输出任何其他文字、解释或围栏标记：
{"pages": [{"title": "页面标题", "summary": "一句话摘要", "content": "markdown 正文，含要点与 [[相关概念]] 链接", "tags": ["标签1"]}]}
"""


class WikiCompiler:
    """单个源文档 → wiki 页面列表。"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0.2,
        )

    def compile(self, source_name: str, text: str) -> List[dict]:
        """编译源文档，返回规范化后的页面 dict 列表。"""
        payload = f"源文档：{source_name}\n\n---\n{text}\n---"
        resp = self.llm.invoke(
            [
                SystemMessage(content=COMPILE_SYSTEM_PROMPT),
                HumanMessage(content=payload),
            ]
        )
        return self._parse(resp.content)

    @staticmethod
    def _parse(content) -> List[dict]:
        """从模型输出中提取并规范化页面 JSON（容忍围栏/前后杂文）。"""
        text = str(content).strip()
        # 1) 优先提取 ```json ... ``` 围栏块
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if m:
            text = m.group(1)
        else:
            # 2) 退化为截取首个 { 到末尾 }
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                text = text[start : end + 1]

        data = json.loads(text)  # 解析失败向上抛，由 ingest 记入失败清单
        if isinstance(data, list):
            raw_pages = data
        elif isinstance(data, dict):
            raw_pages = data.get("pages", [])
        else:
            raise ValueError(f"编译输出结构无法识别: {type(data)}")

        pages = []
        for p in raw_pages:
            title = str(p.get("title", "")).strip()
            content = str(p.get("content", "")).strip()
            if not title or not content:
                continue
            pages.append(
                {
                    "title": title,
                    "summary": str(p.get("summary", "")).strip(),
                    "content": content,
                    "tags": [str(t).strip() for t in p.get("tags", []) if str(t).strip()],
                }
            )
        return pages
