"""配置 —— 从 .env / 环境变量读取，未设置时回退到空值

安全提示：真实密钥统一放在项目根目录的 .env 文件，不要写进本文件。
"""
import os
from pathlib import Path

# 加载项目根目录的 .env 文件（若存在）
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

# ===== API Keys（从 .env 读取，未配置时为空）=====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ===== 数据库连接串（二选一）=====
# MySQL: mysql+pymysql://用户名:密码@主机:端口/数据库名
# PostgreSQL: postgresql+psycopg2://用户名:密码@主机:端口/数据库名
DB_URL = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:root@localhost:3306/VIP_USER",
)

# ===== LLM 模型选择 =====
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-v4-flash")

# ===== LLM API 端点（DeepSeek 官方 API，OpenAI 兼容）=====
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")

# ===== 企业微信群机器人 Webhook（从 .env 读取）=====
WECOM_WEBHOOK_URL = os.getenv("WECOM_WEBHOOK_URL", "")
