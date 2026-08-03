#!/bin/bash
# run_rag.sh —— RAG 系统启动脚本
# 用法（任何目录下都能运行）：
#   ./run_rag.sh --ingest              # 构建索引
#   ./run_rag.sh --rebuild             # 重建索引
#   ./run_rag.sh "你的问题"            # 问答
#   ./run_rag.sh "问题" --show-source  # 问答并显示引用来源

# 切换到脚本所在目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 使用虚拟环境的 Python
PYTHON="$SCRIPT_DIR/bin/python"

# 检查虚拟环境是否存在
if [ ! -f "$PYTHON" ]; then
    echo "错误: 未找到虚拟环境 Python: $PYTHON"
    echo "请确认项目结构完整"
    exit 1
fi

# 运行 RAG 系统
exec "$PYTHON" -m rag.main "$@"
