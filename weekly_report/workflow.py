"""weekly_report/workflow.py —— 每周一统计 ORDER_INFO 表 CREDIT>15 的金额

LangGraph 确定性工作流（不需要 LLM）：
    1. 计算上周时间范围（周一 00:00:00 ~ 周日 23:59:59）
    2. 查询 ORDER_INFO 表，统计 CREDIT>15 的记录数和金额总和
    3. 生成统计报告并写入文件

架构决策说明（为什么用 workflow 而不是 skill）：
    - 本任务是完全确定性的：固定 SQL、固定时间、固定统计逻辑
    - 不需要 LLM 参与决策，因此用确定性 workflow 而非依赖 LLM 的 skill
"""
from datetime import datetime, timedelta
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from sqlalchemy import create_engine, text

from config import DB_URL
from wecom_notifier import send_markdown, build_weekly_report_markdown


# ============================================================
# 状态定义
# ============================================================
class WeeklyReportState(TypedDict):
    """工作流状态。"""
    week_start: str          # 上周一 00:00:00
    week_end: str            # 上周日 23:59:59
    record_count: int        # CREDIT>15 的记录数
    total_amount: float      # CREDIT>15 的金额总和
    report: str              # 生成的报告文本
    generated_at: str        # 报告生成时间
    notified: bool           # 是否已发送企微通知


# ============================================================
# 节点 1：计算上周时间范围
# ============================================================
def compute_last_week(state: WeeklyReportState) -> dict:
    """计算上周的 [周一 00:00:00, 周日 23:59:59] 时间范围。"""
    today = datetime.now()
    # 本周一的日期（weekday() 周一=0）
    this_monday = today - timedelta(days=today.weekday())
    # 上周一 = 本周一 - 7 天
    last_monday = this_monday - timedelta(days=7)
    week_start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = (last_monday + timedelta(days=6)).replace(hour=23, minute=59, second=59)
    return {
        "week_start": week_start.strftime("%Y-%m-%d %H:%M:%S"),
        "week_end": week_end.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 节点 2：查询统计
# ============================================================
def query_and_stats(state: WeeklyReportState) -> dict:
    """查询 ORDER_INFO 表，统计 CREDIT>15 的记录数和金额总和。"""
    engine = create_engine(DB_URL, pool_pre_ping=True)
    sql = text(
        """
        SELECT COUNT(*) AS cnt, COALESCE(SUM(CREDIT), 0) AS total
        FROM ORDER_INFO
        WHERE CREDIT > 15
          AND TIME >= :week_start
          AND TIME <= :week_end
        """
    )
    with engine.connect() as conn:
        row = conn.execute(
            sql,
            {"week_start": state["week_start"], "week_end": state["week_end"]},
        ).fetchone()
    return {
        "record_count": row[0],
        "total_amount": float(row[1] or 0),
    }


# ============================================================
# 节点 3：生成报告
# ============================================================
def generate_report(state: WeeklyReportState) -> dict:
    """生成统计报告文本。"""
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report = (
        "========================================\n"
        "      ORDER_INFO 周统计报告\n"
        "========================================\n"
        f"统计周期: {state['week_start']} ~ {state['week_end']}\n"
        f"统计条件: CREDIT > 15\n"
        "----------------------------------------\n"
        f"记录数:   {state['record_count']}\n"
        f"金额总和: {state['total_amount']:.3f}\n"
        f"生成时间: {generated_at}\n"
        "========================================\n"
    )
    return {"report": report, "generated_at": generated_at}


# ============================================================
# 节点 4：发送企微通知
# ============================================================
def notify(state: WeeklyReportState) -> dict:
    """将统计报告以 Markdown 形式发送到企微群。"""
    md = build_weekly_report_markdown(state)
    ok = send_markdown(md)
    return {"notified": ok}


# ============================================================
# 构建工作流
# ============================================================
def build_workflow():
    """构建每周统计工作流。"""
    graph = StateGraph(WeeklyReportState)

    graph.add_node("compute_last_week", compute_last_week)
    graph.add_node("query_and_stats", query_and_stats)
    graph.add_node("generate_report", generate_report)
    graph.add_node("notify", notify)

    graph.add_edge(START, "compute_last_week")
    graph.add_edge("compute_last_week", "query_and_stats")
    graph.add_edge("query_and_stats", "generate_report")
    graph.add_edge("generate_report", "notify")
    graph.add_edge("notify", END)

    return graph.compile()


if __name__ == "__main__":
    # 手动运行测试
    workflow = build_workflow()
    result = workflow.invoke({})
    print(result["report"])
