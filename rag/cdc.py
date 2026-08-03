"""rag/cdc.py —— 基于 binlog 的 CDC 实时增量更新

监听 MySQL binlog，实时捕获 ORDER_INFO 表的 INSERT/UPDATE/DELETE，
秒级同步到向量库，替代定时全量对比的增量更新。

前置条件（需要开启 MySQL binlog）：
    1. 在 MySQL 配置（如 /etc/my.cnf）中开启：
        [mysqld]
        log_bin=mysql-bin
        binlog_format=ROW
        server-id=1
    2. 重启 MySQL 使配置生效
    3. 确认 binlog 已开启：SHOW VARIABLES LIKE 'log_bin';  # 应为 ON

用法：
    ../bin/python -m rag.cdc --listen        # 启动 CDC 监听（常驻进程）
    ../bin/python -m rag.cdc --resume        # 从上次位置继续（断点续传）
    ../bin/python -m rag.cdc --check-binlog  # 检查 binlog 是否开启

说明：
    - 依赖 python-mysql-replication 库（pip install mysql-replication）
    - 作为常驻进程运行，配合 supervisor/systemd 守护
    - 变更同步到向量库，并清空相关缓存
"""
import argparse
import os

from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    WriteRowsEvent,
    UpdateRowsEvent,
    DeleteRowsEvent,
)
from sqlalchemy import create_engine, text

from rag.config import DB_URL, CHROMA_DIR, COLLECTION_NAME
from rag.embedder import get_embedder
from rag.ingest import row_to_doc
from rag.logging_setup import get_logger

logger = get_logger(__name__)

# 监听的表
_TABLE = "ORDER_INFO"
_DATABASE = "VIP_USER"

# binlog 断点续传文件（记录已处理到的 binlog 位置）
_RESUME_FILE = os.path.join(os.path.dirname(__file__), "logs", "cdc_resume.txt")

# ============================================================
# binlog 连接配置（从 DB_URL 解析）
# ============================================================
def _parse_db_url(db_url: str) -> dict:
    """从 DB_URL 解析 MySQL 连接参数。"""
    # mysql+pymysql://user:pass@host:port/db
    body = db_url.split("://", 1)[1]
    cred, host_part = body.split("@", 1)
    user, pwd = cred.split(":", 1)
    host_port, db = host_part.split("/", 1)
    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host, port = host_port, "3306"
    return {
        "host": host,
        "port": int(port),
        "user": user,
        "passwd": pwd,
        "db": db,
    }


# ============================================================
# 向量库操作
# ============================================================
def _get_vectorstore():
    """获取统一向量库实例（支持 chroma/pgvector/milvus 切换）。"""
    from rag.vectorstore import get_vectorstore
    return get_vectorstore()


def _fetch_row_by_id(order_id) -> dict:
    """从数据库按 ID 查询最新记录（用于 INSERT/UPDATE 同步完整数据）。"""
    engine = create_engine(DB_URL, pool_pre_ping=True)
    sql = text(
        """
        SELECT ID, USER_ID, PID, CREDIT, TIME, PAY_DATE, PAY_TYPE, STATUS,
               PLATFORM, SRC
        FROM ORDER_INFO
        WHERE ID = :id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": order_id}).fetchone()
        if row is None:
            return None
        # 转成 dict（row_to_doc 兼容）
        return {
            "ID": row[0], "USER_ID": row[1], "PID": row[2], "CREDIT": row[3],
            "TIME": row[4], "PAY_DATE": row[5], "PAY_TYPE": row[6],
            "STATUS": row[7], "PLATFORM": row[8], "SRC": row[9],
        }


def _sync_insert(order_id):
    """新增订单 → 写入向量库。"""
    row = _fetch_row_by_id(order_id)
    if row is None:
        logger.warning("CDC: 订单 %s 已不存在，跳过新增", order_id)
        return
    doc = row_to_doc(row)
    vs = _get_vectorstore()
    vs.upsert(ids=[doc.id], documents=[doc.page_content], metadatas=[doc.metadata])
    logger.info("CDC: 新增订单 %s 已同步到向量库", order_id)


def _sync_update(order_id):
    """更新订单 → 覆盖向量库。"""
    row = _fetch_row_by_id(order_id)
    if row is None:
        # 记录被删除则同步删除
        _sync_delete(order_id)
        return
    doc = row_to_doc(row)
    vs = _get_vectorstore()
    vs.upsert(ids=[doc.id], documents=[doc.page_content], metadatas=[doc.metadata])
    logger.info("CDC: 更新订单 %s 已同步到向量库", order_id)


def _sync_delete(order_id):
    """删除订单 → 从向量库删除。"""
    vs = _get_vectorstore()
    doc_id = f"db-{order_id}"
    vs.delete(ids=[doc_id])
    logger.info("CDC: 删除订单 %s 已从向量库移除", order_id)


# ============================================================
# binlog 断点续传
# ============================================================
def _save_resume(binlog_file: str, binlog_pos: int):
    """保存 binlog 处理位置（断点续传）。"""
    try:
        with open(_RESUME_FILE, "w") as f:
            f.write(f"{binlog_file}:{binlog_pos}")
    except Exception as e:
        logger.warning("保存断点失败: %s", e)


def _load_resume():
    """读取上次 binlog 位置。"""
    if not os.path.isfile(_RESUME_FILE):
        return None, None
    try:
        with open(_RESUME_FILE) as f:
            content = f.read().strip()
        if ":" in content:
            fname, pos = content.split(":", 1)
            return fname, int(pos)
    except Exception as e:
        logger.warning("读取断点失败: %s", e)
    return None, None


# ============================================================
# binlog 检查
# ============================================================
def check_binlog() -> bool:
    """检查 MySQL 是否开启 binlog。"""
    engine = create_engine(DB_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        r = conn.execute(text("SHOW VARIABLES LIKE 'log_bin'")).fetchone()
        log_bin = r[1] if r else "OFF"
        if log_bin.upper() != "ON":
            logger.error(
                "MySQL 未开启 binlog（当前 log_bin=%s）。"
                "请先开启 binlog 再启动 CDC，详见模块文档。", log_bin
            )
            return False
        logger.info("binlog 已开启（log_bin=%s）", log_bin)
        return True


# ============================================================
# CDC 主循环
# ============================================================
def listen(resume: bool = False):
    """启动 CDC 监听（常驻进程）。"""
    if not check_binlog():
        return

    conn = _parse_db_url(DB_URL)
    logger.info("开始监听 MySQL binlog（库:%s 表:%s）", conn["db"], _TABLE)

    # 断点续传：从上次位置开始
    resume_file, resume_pos = _load_resume() if resume else (None, None)
    if resume and resume_file:
        logger.info("从断点续传: %s:%s", resume_file, resume_pos)

    stream = BinLogStreamReader(
        connection_settings={
            "host": conn["host"],
            "port": conn["port"],
            "user": conn["user"],
            "passwd": conn["passwd"],
        },
        server_id=1,  # 需唯一，避免与主从复制冲突
        blocking=True,  # 阻塞等待新事件
        resume_stream=resume_file is not None,
        log_file=resume_file,
        log_pos=resume_pos,
        only_events=[WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent],
        only_schemas=[_DATABASE],
        only_tables=[_TABLE],
    )

    try:
        for event in stream:
            for row in event["rows"]:
                if isinstance(event, WriteRowsEvent):
                    order_id = row["values"].get("ID")
                    if order_id is not None:
                        _sync_insert(order_id)
                elif isinstance(event, UpdateRowsEvent):
                    # 更新后值
                    new_values = row.get("after_values", row.get("values", {}))
                    order_id = new_values.get("ID")
                    if order_id is not None:
                        _sync_update(order_id)
                elif isinstance(event, DeleteRowsEvent):
                    order_id = row["values"].get("ID")
                    if order_id is not None:
                        _sync_delete(order_id)

            # 保存断点
            _save_resume(stream.log_file, stream.log_pos)
    except KeyboardInterrupt:
        logger.info("CDC 监听已停止")
    finally:
        stream.close()


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="CDC 实时增量更新")
    parser.add_argument("--listen", action="store_true", help="启动 CDC 监听（常驻）")
    parser.add_argument("--resume", action="store_true", help="从上次断点续传")
    parser.add_argument("--check-binlog", action="store_true", help="检查 binlog 是否开启")
    args = parser.parse_args()

    if args.check_binlog:
        check_binlog()
        return

    if args.listen:
        listen(resume=args.resume)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
