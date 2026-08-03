"""tools/web_search.py —— Web 搜索工具

Researcher Worker 使用。基于 Tavily 搜索。
"""
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from config import TAVILY_API_KEY


def get_web_search_tool():
    """返回 Tavily 搜索工具。若 key 为占位符则返回 mock 工具。"""
    if not TAVILY_API_KEY or TAVILY_API_KEY == "tvly-占位符":
        return _mock_search_tool
    return TavilySearch(
        tavily_api_key=TAVILY_API_KEY,
        max_results=5,
        name="web_search",
        description="搜索互联网，获取实时信息、新闻、资料。输入为搜索关键词。",
    )


@tool
def _mock_search_tool(query: str) -> str:
    """【占位工具】搜索互联网。当前为 mock，填入 TAVILY_API_KEY 后启用真实搜索。"""
    return (
        f"[mock 搜索] 关键词: {query}\n"
        f"提示: 请在 config.py 填入真实的 TAVILY_API_KEY 以启用真实搜索。"
    )
