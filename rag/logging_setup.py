"""rag/logging_setup.py —— 统一日志配置

提供结构化日志（JSON）+ 按天滚动文件 + 控制台输出。

用法：
    from rag.logging_setup import get_logger
    logger = get_logger(__name__)
    logger.info("...")
    logger.error("...", exc_info=True)

特性：
    - 控制台：可读格式
    - 文件：JSON 结构化（便于 ELK/Loki 采集），按天滚动保留 30 天
    - 日志级别通过环境变量 LOG_LEVEL 控制（默认 INFO）
"""
import json
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path

# 日志目录：rag/logs
_LOG_DIR = Path(__file__).resolve().parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志级别（环境变量控制，默认 INFO）
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# 控制台格式（可读）
_CONSOLE_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"

# 已配置的 logger 集合，避免重复配置
_configured = set()


class _JsonFormatter(logging.Formatter):
    """JSON 结构化日志格式器，便于日志采集系统解析。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 异常堆栈
        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)
        # 额外字段（logger.info("msg", extra={"key": "val"})）
        for key, value in record.__dict__.items():
            if key not in ("message", "args", "asctime", "exc_info", "exc_text", "stack_info", "created", "msecs", "relativeCreated", "levelname", "levelno", "name", "pathname", "filename", "module", "lineno", "funcName", "process", "processName", "thread", "threadName", "taskName", "msg", "args"):
                log_entry[key] = value
        return json.dumps(log_entry, ensure_ascii=False)


def _setup_root_logger():
    """配置根 logger（文件 + 控制台），整个进程共用。

    配置 root logger 而非 "rag" logger，这样所有用 get_logger(name)
    创建的子 logger 都能继承统一的级别和 handler。
    """
    root = logging.getLogger()

    if root in _configured:
        return root
    _configured.add(root)

    root.setLevel(_LOG_LEVEL)

    # 控制台 handler（可读格式）
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(_LOG_LEVEL)
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    root.addHandler(console)

    # 文件 handler（JSON 结构化，按天滚动）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(_LOG_DIR / "rag.log"),
        when="midnight",      # 每天 0 点滚动
        interval=1,
        backupCount=30,       # 保留 30 天
        encoding="utf-8",
    )
    file_handler.setLevel(_LOG_LEVEL)
    file_handler.setFormatter(_JsonFormatter())
    root.addHandler(file_handler)

    # 调高第三方库日志级别，避免刷屏（只保留项目自身 INFO 日志）
    _quiet_noisy_loggers()

    return root


def _quiet_noisy_loggers():
    """把第三方库的日志级别调高到 WARNING，避免 INFO 刷屏。"""
    noisy_loggers = [
        "huggingface_hub",
        "sentence_transformers",
        "langchain_openai",
        "langchain",
        "httpx",
        "httpcore",
        "urllib3",
        "chromadb",
        "jieba",
        "openai",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str = None) -> logging.Logger:
    """获取统一配置的 logger。

    Args:
        name: logger 名称（通常传 __name__），None 时返回根 logger
    """
    _setup_root_logger()
    if name:
        return logging.getLogger(name)
    return logging.getLogger()
