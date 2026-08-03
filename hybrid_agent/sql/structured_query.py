"""sql/structured_query.py —— 结构化查询工具

db_agent 使用的工具：
    1. 接收 LLM 从自然语言提取的结构化参数（OrderQuery）
    2. 用 query_templates 的预定义 SQL 模板执行
    3. 返回统计结果

LLM 不直接拼 SQL，只填参数，保证 SQL 安全和可靠。
"""
import json

from langchain_core.tools import tool
from sqlalchemy import create_engine, text

from config import DB_URL
from sql.query_templates import build_sql, OrderQuery, QUERY_SCHEMA_PROMPT


_engine = None


def _get_engine():
    """懒加载数据库引擎。"""
    global _engine
    if _engine is None:
        _engine = create_engine(DB_URL, pool_pre_ping=True)
    return _engine


@tool
def query_order_stats(query_json: str) -> str:
    """按结构化参数查询 ORDER_INFO 表的统计信息（记录数、金额总和、最大/最小金额）。

    参数 query_json 是一个 JSON 字符串，包含以下可选字段：
    - min_credit: 最小金额 (float)
    - max_credit: 最大金额 (float)
    - start_time: 开始日期 (str, YYYY-MM-DD)
    - end_time: 结束日期 (str, YYYY-MM-DD)
    - status: 状态 (int)
    - pay_type: 支付类型 (int)
    - user_id: 用户ID (int)
    - pid: 产品ID (int)
    - platform: 平台 (str)
    - src: 来源 (str)

    示例: {"min_credit": 15, "status": 1}
    """
    try:
        # 解析参数
        query = json.loads(query_json) if query_json else {}
        # 构建 SQL
        sql, params = build_sql(query)
        if not params:
            return "未提供任何过滤条件，请提供至少一个查询条件。"

        # 执行
        engine = _get_engine()
        with engine.connect() as conn:
            row = conn.execute(text(sql), params).fetchone()

        result = {
            "conditions": query,
            "record_count": row[0],
            "total_amount": float(row[1] or 0),
            "max_credit": float(row[2] or 0),
            "min_credit": float(row[3] or 0),
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"查询出错: {type(e).__name__}: {e}"


# 供 db_agent 使用的工具列表
STRUCTURED_QUERY_TOOLS = [query_order_stats]

# 供 db_agent 的 system prompt 使用
STRUCTURED_QUERY_PROMPT = QUERY_SCHEMA_PROMPT
