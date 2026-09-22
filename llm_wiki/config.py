"""llm_wiki/config.py —— LLM Wiki 模块配置

复用项目根目录 .env；LLM 走 DeepSeek（OpenAI 兼容），与 rag 模块保持一致。
本模块独立于 rag（仅消费 rag/knowledge 目录下的 md 文件）。

LangSmith 自动追踪：配置了 LANGSMITH_API_KEY 时注入环境变量，
LangChain 调用（编译/问答）自动进 trace，项目名默认 llm-wiki。
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

# ===== 摄入源：rag/knowledge 下的 md 文件 =====
KNOWLEDGE_DIR = Path(
    os.getenv("WIKI_KNOWLEDGE_DIR", str(Path(__file__).resolve().parent.parent / "rag" / "knowledge"))
)

# ===== 编译产物目录（默认本模块下的 wiki/）=====
WIKI_DIR = Path(os.getenv("WIKI_DIR", str(Path(__file__).resolve().parent / "wiki")))

# ===== LLM（DeepSeek，OpenAI 兼容）=====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-v4-flash")

# ===== LangSmith 自动追踪（可选）=====
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "llm-wiki")
LANGSMITH_ENABLED = bool(LANGSMITH_API_KEY)

if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
    os.environ.setdefault("LANGSMITH_PROJECT", LANGSMITH_PROJECT)
    os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
