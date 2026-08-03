"""rag/eval/stub_vertexai.py —— ragas 兼容 stub

问题背景：
    ragas 0.4.3 在 `ragas/llms/base.py` 顶层硬导入
    `langchain_community.chat_models.vertexai.ChatVertexAI`，
    但新版 langchain-community（>=0.3.x）已移除该模块，导致 ragas 无法导入。

解决方案：
    在导入 ragas 之前，向 sys.modules 注入一个兼容 stub 模块，
    提供一个最小可用的 ChatVertexAI 占位类。本项目实际使用 OpenAI
    兼容接口（DeepSeek），不会用到 VertexAI，因此 stub 只需满足导入。

用法：
    from rag.eval.stub_vertexai import apply_vertexai_stub
    apply_vertexai_stub()
    import ragas  # 此时可正常导入
"""
import sys
import types

# 模块路径：langchain_community.chat_models.vertexai
_MODULE_PATH = "langchain_community.chat_models.vertexai"


class _ChatVertexAIStub:
    """ChatVertexAI 占位类。

    仅用于让 ragas 的 `MULTIPLE_COMPLETION_SUPPORTED` 列表能引用它，
    实际不会被实例化或调用。
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "ChatVertexAI 是兼容占位类，本项目不支持 VertexAI。"
            "请使用 OpenAI 兼容接口（DeepSeek）。"
        )


def _build_stub_module() -> types.ModuleType:
    """构造一个包含 ChatVertexAI 占位类的模块对象。"""
    module = types.ModuleType(_MODULE_PATH)
    module.__file__ = f"{_MODULE_PATH}.py (stub)"
    module.ChatVertexAI = _ChatVertexAIStub
    return module


def apply_vertexai_stub() -> None:
    """向 sys.modules 注入 vertexai stub（若尚未注入）。"""
    if _MODULE_PATH not in sys.modules:
        sys.modules[_MODULE_PATH] = _build_stub_module()
        print(f"[eval] 已注入兼容 stub: {_MODULE_PATH}")
