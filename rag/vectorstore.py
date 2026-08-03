"""rag/vectorstore.py —— 统一向量库接口层

支持三种后端可切换：Chroma / pgvector / Milvus。
通过配置 VECTOR_STORE_TYPE（环境变量或 .env）选择，运行时无需改代码。

统一接口（三种后端都实现）：
    add(ids, documents, metadatas)                          # 新增（重复 ID 覆盖）
    upsert(ids, documents, metadatas)                       # 新增或更新
    update(ids, documents)                                  # 更新
    delete(ids)                                             # 删除
    get(include) -> {"ids", "documents", "metadatas"}       # 获取全部
    similarity_search_with_relevance_scores(query, k, filter)  # 相似度检索

用法：
    from rag.vectorstore import get_vectorstore
    vs = get_vectorstore()
    vs.upsert(ids=["db-1"], documents=["内容"], metadatas=[{"source": "db"}])
    docs = vs.similarity_search_with_relevance_scores("问题", k=5, filter=None)
"""
from typing import List, Optional

from langchain_core.documents import Document

from rag.config import (
    VECTOR_STORE_TYPE,
    CHROMA_DIR,
    COLLECTION_NAME,
    PGVECTOR_URL,
    MILVUS_HOST,
    MILVUS_PORT,
)
from rag.embedder import get_embedder
from rag.logging_setup import get_logger

logger = get_logger(__name__)


# ============================================================
# 统一接口基类
# ============================================================
class BaseVectorStore:
    """向量库统一接口。各后端继承并实现。"""

    def add(self, ids: List[str], documents: List[str], metadatas: List[dict]):
        raise NotImplementedError

    def upsert(self, ids: List[str], documents: List[str], metadatas: List[dict]):
        raise NotImplementedError

    def update(self, ids: List[str], documents: List[str], metadatas: List[dict] = None):
        raise NotImplementedError

    def delete(self, ids: List[str]):
        raise NotImplementedError

    def get(self, include: Optional[List[str]] = None) -> dict:
        raise NotImplementedError

    def similarity_search_with_relevance_scores(
        self, query: str, k: int, filter: Optional[dict] = None
    ) -> List:
        raise NotImplementedError


# ============================================================
# Chroma 实现
# ============================================================
class ChromaStore(BaseVectorStore):
    """Chroma 后端（单机文件存储，默认）。"""

    def __init__(self):
        from langchain_chroma import Chroma

        self._store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embedder(),
            persist_directory=CHROMA_DIR,
        )

    def add(self, ids, documents, metadatas):
        self._store.add_documents(
            [Document(page_content=d, metadata=m) for d, m in zip(documents, metadatas)],
            ids=ids,
        )

    def upsert(self, ids, documents, metadatas):
        # Chroma: add_documents 用稳定 ID，重复 ID 自动覆盖（upsert 行为）
        self._store.add_documents(
            [Document(page_content=d, metadata=m) for d, m in zip(documents, metadatas)],
            ids=ids,
        )

    def update(self, ids, documents, metadatas=None):
        # Chroma: update_documents 需要 metadatas，缺失时用空 dict
        self._store.update_documents(
            ids,
            [Document(page_content=d, metadata=m or {}) for d, m in zip(documents, metadatas or [{} for _ in ids])],
        )

    def delete(self, ids):
        self._store.delete(ids=list(ids))

    def get(self, include=None):
        return self._store.get(include=include or ["documents", "metadatas"])

    def similarity_search_with_relevance_scores(self, query, k, filter=None):
        return self._store.similarity_search_with_relevance_scores(query, k=k, filter=filter)


# ============================================================
# pgvector 实现
# ============================================================
class PgVectorStore(BaseVectorStore):
    """pgvector 后端（PostgreSQL + pgvector 扩展）。

    需要 PostgreSQL 服务 + pgvector 扩展：
        1. 启动 PostgreSQL（可用 Docker：pgvector/pgvector）
        2. 创建数据库并启用扩展：CREATE EXTENSION IF NOT EXISTS vector;
    """

    def __init__(self):
        from langchain_postgres import PGVector

        self._store = PGVector(
            connection=PGVECTOR_URL,
            embeddings=get_embedder(),
            collection_name=COLLECTION_NAME,
            use_jsonb=True,
        )

    def add(self, ids, documents, metadatas):
        self._store.add_documents(
            [Document(page_content=d, metadata=m) for d, m in zip(documents, metadatas)],
            ids=ids,
        )

    def upsert(self, ids, documents, metadatas):
        # pgvector 的 add_documents 用稳定 ID 时重复会覆盖
        self._store.add_documents(
            [Document(page_content=d, metadata=m) for d, m in zip(documents, metadatas)],
            ids=ids,
        )

    def update(self, ids, documents, metadatas=None):
        # pgvector 无 update_documents，用 add 覆盖
        self._store.add_documents(
            [Document(page_content=d, metadata=m or {}) for d, m in zip(documents, metadatas or [{} for _ in documents])],
            ids=ids,
        )

    def delete(self, ids):
        self._store.delete(ids=list(ids))

    def get(self, include=None):
        # pgvector 通过 SQL 查询
        import sqlalchemy
        from sqlalchemy import create_engine, text

        engine = create_engine(PGVECTOR_URL)
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT cmetadata, document FROM langchain_pg_embedding")
            ).fetchall()
        return {
            "ids": [i for i in range(len(rows))],
            "documents": [r[1] for r in rows],
            "metadatas": [r[0] for r in rows],
        }

    def similarity_search_with_relevance_scores(self, query, k, filter=None):
        return self._store.similarity_search_with_relevance_scores(query, k=k)


# ============================================================
# Milvus 实现
# ============================================================
class MilvusStore(BaseVectorStore):
    """Milvus 后端（专业向量数据库）。

    需要 Milvus 服务（可用 Docker 启动）：
        docker run -d --name milvus -p 19530:19530 -p 9091:9091 milvusdb/milvus:latest
    """

    def __init__(self):
        from langchain_milvus import Milvus

        self._store = Milvus(
            embedding_function=get_embedder(),
            collection_name=COLLECTION_NAME,
            connection_args={"host": MILVUS_HOST, "port": MILVUS_PORT},
            auto_id=False,
        )

    def add(self, ids, documents, metadatas):
        self._store.add_documents(
            [Document(page_content=d, metadata=m) for d, m in zip(documents, metadatas)],
            ids=ids,
        )

    def upsert(self, ids, documents, metadatas):
        self._store.add_documents(
            [Document(page_content=d, metadata=m) for d, m in zip(documents, metadatas)],
            ids=ids,
        )

    def update(self, ids, documents, metadatas=None):
        self._store.add_documents(
            [Document(page_content=d, metadata=m or {}) for d, m in zip(documents, metadatas or [{} for _ in documents])],
            ids=ids,
        )

    def delete(self, ids):
        # Milvus 按主键删除
        for i in ids:
            self._store.delete(ids=[i])

    def get(self, include=None):
        # Milvus 全量查询
        return self._store.get(include=include or ["documents", "metadatas"])

    def similarity_search_with_relevance_scores(self, query, k, filter=None):
        return self._store.similarity_search_with_relevance_scores(query, k=k)


# ============================================================
# 工厂函数
# ============================================================
_STORE_CACHE = {}


def get_vectorstore() -> BaseVectorStore:
    """根据 VECTOR_STORE_TYPE 返回对应的向量库实例（单例缓存）。"""
    store_type = VECTOR_STORE_TYPE.lower()
    if store_type in _STORE_CACHE:
        return _STORE_CACHE[store_type]

    logger.info("使用向量库后端: %s", store_type)
    if store_type == "chroma":
        store = ChromaStore()
    elif store_type == "pgvector":
        store = PgVectorStore()
    elif store_type == "milvus":
        store = MilvusStore()
    else:
        raise ValueError(f"不支持的向量库类型: {store_type}（可选 chroma/pgvector/milvus）")

    _STORE_CACHE[store_type] = store
    return store
