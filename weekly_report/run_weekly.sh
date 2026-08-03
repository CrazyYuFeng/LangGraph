#!/bin/bash
# run_weekly.sh —— 每周一触发统计工作流的脚本
# 用法：由 cron 调用，或手动执行
#
# cron 配置（每周一 09:00 执行）：
#   0 9 * * 1 /Users/tme8000/workspace/LangGraph/weekly_report/run_weekly.sh
#
# 注意：脚本需在项目根目录下运行，以便正确引用 venv 和 config

# 切换到脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Python 解释器（使用项目的 venv）
PYTHON="../bin/python"

# 日志文件
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/weekly_report_$(date +%Y%m%d_%H%M%S).log"

echo "===== 开始执行每周统计任务 $(date) =====" >> "$LOG_FILE"
echo "工作目录: $SCRIPT_DIR" >> "$LOG_FILE"

# 运行工作流并保存报告
"$PYTHON" main.py --save >> "$LOG_FILE" 2>&1

# 记录退出状态
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "===== 任务成功完成 $(date) =====" >> "$LOG_FILE"
else
    echo "===== 任务失败，退出码 $EXIT_CODE $(date) =====" >> "$LOG_FILE"
fi

echo "日志已保存到: $LOG_FILE"
exit $EXIT_CODE
