"""tools/python_repl.py —— Python 代码执行工具

Coder Worker 使用。基于 exec + 捕获 stdout 实现，不依赖被弃用的 langchain-experimental。
"""
import io
import contextlib

from langchain_core.tools import tool


def _run_python(code: str) -> str:
    """执行 Python 代码，捕获 stdout 和返回值。"""
    namespace = {}
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, namespace)
        return output.getvalue()
    except Exception as e:
        return f"执行出错: {type(e).__name__}: {e}"


@tool
def python_repl(code: str) -> str:
    """执行 Python 代码并返回结果。用于数学计算、数据分析、脚本执行等。
    输入应为可独立运行的完整 Python 代码。"""
    result = _run_python(code)
    return result if result else "（代码执行成功，无输出）"
