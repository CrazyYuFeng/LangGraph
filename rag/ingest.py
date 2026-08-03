"""rag/ingest.py —— 数据入库（索引构建）

支持两种数据源：
    1. 数据库业务数据（按记录切分 + 元数据）
    2. 本地文件（txt/md，按语义切分）

Chunk 优化策略（对应 RAG_OPTIMIZATION.md）：
    - 业务数据：按记录切分，每条记录一个 chunk + 元数据标签
    - 文本文件：按语义边界切分（段落/句子），重叠保留上下文
"""
import os
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from sqlalchemy import create_engine, text

from rag.config import DB_URL, CHROMA_DIR, COLLECTION_NAME, KNOWLEDGE_DIR
from rag.embedder import get_embedder
from rag.vectorstore import get_vectorstore
from rag.logging_setup import get_logger

logger = get_logger(__name__)


# ============================================================
# 数据源 1：数据库业务数据（ORDER_INFO 表）
# ============================================================
# ORDER_INFO 表的字段顺序（与 SELECT 语句一致）
_ORDER_COLUMNS = ["ID", "USER_ID", "PID", "CREDIT", "TIME", "PAY_DATE", "PAY_TYPE", "STATUS", "PLATFORM", "SRC"]


def row_to_doc(row) -> Document:
    """把 ORDER_INFO 表的一行记录转换为 Document（chunk + 元数据）。

    供 load_db_records（批量入库）和 cdc（单条变更）复用，保证 ID 和
    文本格式一致。

    Args:
        row: 一行记录（支持序列解包或 dict）

    Returns:
        Document，id 为 "db-{订单ID}"
    """
    # 兼容 dict 和序列两种行表示
    if hasattr(row, "keys"):  # dict-like
        r = [row.get(c) for c in _ORDER_COLUMNS]
    else:
        r = list(row)

    content = (
        f"订单ID:{r[0]} 用户ID:{r[1]} 产品ID:{r[2]} "
        f"金额(CREDIT):{r[3]} 下单时间:{r[4]} 支付时间:{r[5]} "
        f"支付类型:{r[6]} 状态:{r[7]} 平台:{r[8]} 来源:{r[9]}"
    )
    metadata = {
        "source": "db",
        "table": "ORDER_INFO",
        "order_id": str(r[0]),
        "user_id": str(r[1]),
        "date": str(r[4]) if r[4] else "",
        "status": str(r[7]),
    }
    doc = Document(page_content=content, metadata=metadata)
    doc.id = f"db-{r[0]}"
    return doc


def load_db_records(limit: int = 1000) -> List[Document]:
    """从 ORDER_INFO 表加载业务记录，按记录切分 + 元数据。"""
    engine = create_engine(DB_URL, pool_pre_ping=True)
    sql = text(
        """
        SELECT ID, USER_ID, PID, CREDIT, TIME, PAY_DATE, PAY_TYPE, STATUS,
               PLATFORM, SRC
        FROM ORDER_INFO
        ORDER BY TIME DESC
        LIMIT :limit
        """
    )
    docs = []
    with engine.connect() as conn:
        rows = conn.execute(sql, {"limit": limit}).fetchall()
        for row in rows:
            docs.append(row_to_doc(row))
    return docs


# ============================================================
# 数据源 2：本地文件（txt/md）
# ============================================================
def load_local_files() -> List[Document]:
    """加载 KNOWLEDGE_DIR 下的 txt/md 文件，按语义切分。"""
    if not os.path.isdir(KNOWLEDGE_DIR):
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],  # 中文分隔符
    )

    docs = []
    for fname in os.listdir(KNOWLEDGE_DIR):
        fpath = os.path.join(KNOWLEDGE_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in (".txt", ".md"):
            continue
        with open(fpath, encoding="utf-8") as f:
            text_content = f.read()
        chunks = splitter.split_text(text_content)
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={"source": "file", "file": fname, "chunk": i},
            )
            # 稳定 ID：source + 文件名 + chunk下标，避免重复入库
            doc.id = f"file-{fname}-{i}"
            docs.append(doc)
    return docs


# ============================================================
# 索引构建
# ============================================================
def build_index(rebuild: bool = False):
    """构建向量索引。rebuild=True 时清空重建。"""
    # 加载所有文档
    db_docs = load_db_records()
    file_docs = load_local_files()
    all_docs = db_docs + file_docs

    if not all_docs:
        logger.warning("没有可入库的数据")
        return None

    # 获取统一向量库（支持 chroma/pgvector/milvus 切换）
    vectorstore = get_vectorstore()

    if rebuild:
        # 清空重建：删除已有的所有 ID
        existing = vectorstore.get()
        if existing.get("ids"):
            vectorstore.delete(existing["ids"])
            logger.info("已清空旧索引 %s 条", len(existing["ids"]))

    # 入库（用稳定 ID，重复入库时自动覆盖，不会累积重复）
    ids = [d.id for d in all_docs]
    vectorstore.add(
        ids=ids,
        documents=[d.page_content for d in all_docs],
        metadatas=[d.metadata for d in all_docs],
    )
    logger.info("已入库 %s 条文档（数据库 %s 条，本地文件 %s 条）", len(all_docs), len(db_docs), len(file_docs))
    return vectorstore


# ============================================================
# 增量更新（企业级：只处理变更，不全量重建）
# ============================================================
def incremental_update() -> dict:
    """增量更新索引。

    流程：
        1. 加载当前所有文档（数据库 + 本地文件）
        2. 对比索引中已有的 ID
        3. 新增/修改 → upsert（有则更新，无则新增）
        4. 已删除（索引有但数据源无）→ 从索引删除

    返回：
        {"added": n, "updated": n, "deleted": n, "unchanged": n}
    """
    # 加载当前数据源的所有文档
    db_docs = load_db_records()
    file_docs = load_local_files()
    all_docs = db_docs + file_docs

    # 当前数据源的 ID 集合
    current_ids = set(d.id for d in all_docs)
    # 当前文档的 id -> doc 映射
    doc_map = {d.id: d for d in all_docs}

    # 获取统一向量库（不重建）
    vectorstore = get_vectorstore()

    # 获取索引中已有的所有 ID
    existing_ids = set(vectorstore.get()["ids"])

    # 1. 新增的文档（数据源有，索引无）
    add_ids = current_ids - existing_ids
    if add_ids:
        add_docs = [doc_map[i] for i in add_ids]
        vectorstore.add(
            ids=list(add_ids),
            documents=[d.page_content for d in add_docs],
            metadatas=[d.metadata for d in add_docs],
        )

    # 2. 更新的文档（数据源有，索引也有 → 内容可能变了，重新覆盖）
    update_ids = current_ids & existing_ids
    if update_ids:
        update_docs = [doc_map[i] for i in update_ids]
        vectorstore.update(
            list(update_ids),
            [d.page_content for d in update_docs],
            [d.metadata for d in update_docs],
        )

    # 3. 删除的文档（索引有，但数据源已无）
    delete_ids = existing_ids - current_ids
    if delete_ids:
        vectorstore.delete(list(delete_ids))

    # 统计
    added = len(add_ids)       # 新增
    updated = len(update_ids)  # 更新
    deleted = len(delete_ids)  # 删除

    logger.info("增量更新完成：新增 %s 条，更新 %s 条，删除 %s 条，当前总数 %s 条", added, updated, deleted, len(current_ids))

    return {"added": added, "updated": updated, "deleted": deleted, "total": len(current_ids)}


if __name__ == "__main__":
    import sys
    if "--rebuild" in sys.argv:
        build_index(rebuild=True)
    else:
        incremental_update()
