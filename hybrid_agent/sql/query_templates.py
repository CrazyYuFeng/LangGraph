"""sql/query_templates.py —— ORDER_INFO 结构化查询模板

核心设计：
    - 预定义所有可过滤字段及其类型、描述
    - LLM 只负责从自然语言中提取字段值（结构化参数）
    - 代码用预定义 SQL 模板 + 参数执行，LLM 不直接拼 SQL

这样做的优势：
    1. SQL 是写死的、经过测试的，不会出错
    2. LLM 只需要理解意图 + 提取参数，不需要"说很多"写 SQL
    3. 条件灵活组合，但都在可控字段范围内
    4. 安全：参数化查询，防注入
"""
from typing import Optional, TypedDict


# ============================================================
# 查询参数定义（LLM 只填这些字段）
# ============================================================
class OrderQuery(TypedDict, total=False):
    """ORDER_INFO 查询参数。LLM 从自然语言中提取。"""
    # 金额过滤
    min_credit: Optional[float]     # CREDIT 最小金额
    max_credit: Optional[float]     # CREDIT 最大金额
    # 时间过滤（TIME 字段）
    start_time: Optional[str]       # 开始时间，格式 YYYY-MM-DD
    end_time: Optional[str]         # 结束时间，格式 YYYY-MM-DD
    # 状态过滤
    status: Optional[int]           # STATUS 状态
    pay_type: Optional[int]         # PAY_TYPE 支付类型
    # 用户/产品过滤
    user_id: Optional[int]          # USER_ID 用户
    pid: Optional[int]              # PID 产品
    # 其他
    platform: Optional[str]         # PLATFORM 平台
    src: Optional[str]              # SRC 来源


# 字段说明（给 LLM 看的 schema）
QUERY_SCHEMA = {
    "min_credit": {"type": "float", "desc": "CREDIT 最小金额，如 15 表示 CREDIT>15"},
    "max_credit": {"type": "float", "desc": "CREDIT 最大金额，如 100 表示 CREDIT<100"},
    "start_time": {"type": "str", "format": "YYYY-MM-DD", "desc": "开始时间，TIME>=该日期"},
    "end_time": {"type": "str", "format": "YYYY-MM-DD", "desc": "结束时间，TIME<=该日期"},
    "status": {"type": "int", "desc": "STATUS 状态，如 1"},
    "pay_type": {"type": "int", "desc": "PAY_TYPE 支付类型"},
    "user_id": {"type": "int", "desc": "USER_ID 用户ID"},
    "pid": {"type": "int", "desc": "PID 产品ID"},
    "platform": {"type": "str", "desc": "PLATFORM 平台"},
    "src": {"type": "str", "desc": "SRC 来源"},
}

# 给 LLM 的说明文本
QUERY_SCHEMA_PROMPT = """请从用户的查询需求中提取以下可选过滤参数，返回 JSON 对象（只包含用户明确提到的条件，没提到的字段不要出现）：

字段说明：
- min_credit: 最小金额（float），如"CREDIT>15"→15，"金额大于20"→20
- max_credit: 最大金额（float），如"CREDIT<100"→100
- start_time: 开始日期（str, YYYY-MM-DD），如"上周"→(计算后日期)，"7月1日"→"2026-07-01"
- end_time: 结束日期（str, YYYY-MM-DD）
- status: 状态（int），如"状态1"→1
- pay_type: 支付类型（int）
- user_id: 用户ID（int）
- pid: 产品ID（int）
- platform: 平台（str）
- src: 来源（str）

只输出 JSON，不要输出其他内容。"""


# ============================================================
# SQL 模板（写死的，参数化查询，防注入）
# ============================================================
def build_sql(query: OrderQuery) -> tuple[str, dict]:
    """根据参数构建安全的参数化 SQL。"""
    conditions = []
    params = {}

    if query.get("min_credit") is not None:
        conditions.append("CREDIT > :min_credit")
        params["min_credit"] = query["min_credit"]
    if query.get("max_credit") is not None:
        conditions.append("CREDIT < :max_credit")
        params["max_credit"] = query["max_credit"]
    if query.get("start_time"):
        conditions.append("TIME >= :start_time")
        params["start_time"] = query["start_time"]
    if query.get("end_time"):
        conditions.append("TIME <= :end_time")
        params["end_time"] = query["end_time"]
    if query.get("status") is not None:
        conditions.append("STATUS = :status")
        params["status"] = query["status"]
    if query.get("pay_type") is not None:
        conditions.append("PAY_TYPE = :pay_type")
        params["pay_type"] = query["pay_type"]
    if query.get("user_id") is not None:
        conditions.append("USER_ID = :user_id")
        params["user_id"] = query["user_id"]
    if query.get("pid") is not None:
        conditions.append("PID = :pid")
        params["pid"] = query["pid"]
    if query.get("platform"):
        conditions.append("PLATFORM = :platform")
        params["platform"] = query["platform"]
    if query.get("src"):
        conditions.append("SRC = :src")
        params["src"] = query["src"]

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = (
        "SELECT COUNT(*) AS cnt, "
        "COALESCE(SUM(CREDIT),0) AS total_amount, "
        "COALESCE(MAX(CREDIT),0) AS max_credit, "
        "COALESCE(MIN(CREDIT),0) AS min_credit "
        f"FROM ORDER_INFO{where_clause}"
    )
    return sql, params
