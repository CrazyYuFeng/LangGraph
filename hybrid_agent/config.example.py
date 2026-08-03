"""配置模板 —— 复制本文件为 config.py 并填入真实值

使用说明：
    1. 复制本文件为 config.py
    2. 填入真实的 API key 和数据库连接串
    3. 代码会优先读取环境变量，未设置时回退到 config.py 的值

安全提示：config.py 含敏感信息，请加入 .gitignore，不要提交到仓库。
"""

import os

# ===== API Keys（占位符，请填入真实值）=====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-占位符")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "tvly-占位符")

# ===== 数据库连接串（二选一）=====
# MySQL: mysql+pymysql://用户名:密码@主机:端口/数据库名
# PostgreSQL: postgresql+psycopg2://用户名:密码@主机:端口/数据库名
DB_URL = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:password@localhost:3306/mydb",
)

# ===== LLM 模型选择 =====
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-v4-flash")

# ===== LLM API 端点（DeepSeek 官方 API，OpenAI 兼容）=====
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")

# ===== 企业微信群机器人 Webhook（占位符，请填入真实值）=====
WECOM_WEBHOOK_URL = os.getenv(
    "WECOM_WEBHOOK_URL",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=占位符",
)
