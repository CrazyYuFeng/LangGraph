"""mock 处理 —— 当 API key 为占位符时，提供不依赖真实 LLM 的回退逻辑

用途：在未配置真实 OPENAI_API_KEY 时，验证整个多智能体架构链路
（Supervisor 路由 → Worker 工具执行 → 返回结果）能否跑通。
"""
from langchain_core.messages import AIMessage

from config import OPENAI_API_KEY


def is_mock_mode() -> bool:
    """判断是否处于 mock 模式（API key 为占位符）。"""
    return not OPENAI_API_KEY or OPENAI_API_KEY == "sk-占位符"


def run_tool_and_reply(tool_fn, tool_args: dict) -> dict:
    """直接调用工具并构造 AI 回复（mock 模式用，跳过 ReAct 循环）。"""
    result = tool_fn.invoke(tool_args)
    return {
        "messages": [
            AIMessage(
                content=(
                    f"[mock 模式] 已调用工具 `{tool_fn.name}`，结果如下：\n"
                    f"<result>\n{result}\n</result>\n\n"
                    f"（提示：配置真实的 OPENAI_API_KEY 后，Worker 将使用 ReAct 循环自主调用工具）"
                )
            )
        ]
    }
