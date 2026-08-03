#!/bin/bash
# run_cdc.sh —— CDC 实时增量更新启动脚本
# 用法：
#   ./run_cdc.sh           # 启动 CDC 监听（常驻进程）
#   ./run_cdc.sh --resume  # 从上次断点续传
#   ./run_cdc.sh --check   # 检查 binlog 是否开启

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 使用虚拟环境 Python
PYTHON="$SCRIPT_DIR/bin/python"

# 日志目录
LOG_DIR="$SCRIPT_DIR/rag/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cdc_$(date +%Y%m%d).log"

case "$1" in
    --resume)
        echo "===== CDC 启动（断点续传）$(date) =====" >> "$LOG_FILE"
        exec "$PYTHON" -m rag.cdc --listen --resume >> "$LOG_FILE" 2>&1
        ;;
    --check)
        exec "$PYTHON" -m rag.cdc --check-binlog
        ;;
    *)
        echo "===== CDC 启动 $(date) =====" >> "$LOG_FILE"
        exec "$PYTHON" -m rag.cdc --listen >> "$LOG_FILE" 2>&1
        ;;
esac
