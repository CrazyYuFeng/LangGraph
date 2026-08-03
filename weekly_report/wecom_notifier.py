"""wecom_notifier.py —— 企业微信群机器人通知

通过群机器人 Webhook 发送 Markdown 消息到企业微信群。
文档参考: https://developer.work.weixin.qq.com/document/path/91770
"""
import json

import requests

from config import WECOM_WEBHOOK_URL


def send_markdown(content: str) -> bool:
    """发送 Markdown 消息到企微群。返回是否成功。"""
    if not WECOM_WEBHOOK_URL or "占位符" in WECOM_WEBHOOK_URL:
        print("[企微通知] 未配置有效的 WECOM_WEBHOOK_URL，跳过发送。")
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content,
        },
    }
    try:
        resp = requests.post(WECOM_WEBHOOK_URL, json=payload, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            print("[企微通知] 发送成功")
            return True
        else:
            print(f"[企微通知] 发送失败: {data}")
            return False
    except Exception as e:
        print(f"[企微通知] 发送异常: {type(e).__name__}: {e}")
        return False


def build_weekly_report_markdown(state: dict) -> str:
    """根据工作流状态构建周统计报告的 Markdown 文本。"""
    return (
        f"## 📊 ORDER_INFO 周统计报告\n"
        f"> 统计周期：{state['week_start']} ~ {state['week_end']}\n"
        f"> 统计条件：**CREDIT > 15**\n\n"
        f"---\n"
        f"- **记录数**：{state['record_count']}\n"
        f"- **金额总和**：<font color=\"warning\">{state['total_amount']:.3f}</font>\n\n"
        f"<font color=\"comment\">生成时间：{state.get('generated_at', '')}</font>"
    )
