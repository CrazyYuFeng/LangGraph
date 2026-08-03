"""weekly_report/config.py —— 每周统计工作流的配置

独立于 hybrid_agent 的配置，仅包含本工作流需要的数据库连接信息。
真实密钥统一放在项目根目录的 .env 文件。
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

# ===== 数据库连接串 =====
DB_URL = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:root@localhost:3306/VIP_USER",
)

# ===== 企业微信群机器人 Webhook（从 .env 读取）=====
# 在企微群里添加机器人后获取，形如:
# https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx-xxxx
WECOM_WEBHOOK_URL = os.getenv("WECOM_WEBHOOK_URL", "")
