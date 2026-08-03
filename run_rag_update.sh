#!/bin/bash
# run_rag_update.sh —— RAG 定时增量更新脚本
# 用法：由 cron 调用，或手动执行
#
# cron 配置（每天 02:00 更新一次）：
#   0 2 * * * /Users/tme8000/workspace/LangGraph/run_rag_update.sh
#
# 也可用 --rebuild 全量重建：
#   ./run_rag_update.sh --rebuild

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 使用虚拟环境 Python
PYTHON="$SCRIPT_DIR/bin/python"

# 日志目录
LOG_DIR="$SCRIPT_DIR/rag/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/rag_update_$(date +%Y%m%d).log"  # 按天记录

echo "===== RAG 更新开始 $(date) =====" >> "$LOG_FILE"

# 运行增量更新
"$PYTHON" -m rag.update "$@" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "===== RAG 更新成功 $(date) =====" >> "$LOG_FILE"
else
    echo "===== RAG 更新失败，退出码 $EXIT_CODE $(date) =====" >> "$LOG_FILE"
fi

echo "日志已保存到: $LOG_FILE"
exit $EXIT_CODE
