"""rag/config.py —— RAG 系统配置

包含：embedding 模型、向量库路径、数据库连接、LLM 配置。

支持从项目根目录的 .env 文件读取配置（优先于默认值）。
"""
import os
from pathlib import Path

# 加载项目根目录的 .env 文件（若存在）
try:
    from dotenv import load_dotenv

    # 项目根目录 = rag/ 的上一级
    _ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass  # 未安装 python-dotenv 时跳过，仅用系统环境变量

# ===== embedding 模型（本地开源，免费离线）=====
# bge-small-zh-v1.5：中文效果好，体积小（约 100MB）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

# ===== 向量库（可切换）=====
# 类型：chroma / pgvector / milvus
VECTOR_STORE_TYPE = os.getenv("VECTOR_STORE_TYPE", "chroma")

# Chroma 持久化目录
CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.join(os.path.dirname(__file__), "chroma_db"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "business_docs")

# pgvector 连接（PostgreSQL + pgvector 扩展）
PGVECTOR_URL = os.getenv(
    "PGVECTOR_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/rag",
)

# Milvus 连接
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))

# ===== 检索参数 =====
TOP_K = int(os.getenv("TOP_K", "5"))          # 召回数量
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.4"))  # 相似度阈值（上下文污染过滤）

# ===== 数据库连接 =====
DB_URL = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:root@localhost:3306/VIP_USER",
)

# ===== LLM 配置（DeepSeek）=====
# 注意：密钥统一从 .env 读取，不写死在代码里。
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-v4-flash")

# ===== 本地文件知识库目录 =====
# 放入需要入库的文档（txt/md/pdf 等）
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", os.path.join(os.path.dirname(__file__), "knowledge"))

# ===== Redis 缓存（查询缓存）=====
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 缓存过期时间（秒），默认 1 小时

# ===== Langfuse 可观测性（可选）=====
# 未配置时自动禁用 trace，不影响正常功能。
# 在 https://cloud.langfuse.com 创建项目后填入以下 key。
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
LANGFUSE_ENABLED = bool(
    LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
)  # 两个 key 都配置才启用
