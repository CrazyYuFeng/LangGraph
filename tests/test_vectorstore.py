"""tests/test_vectorstore.py —— 向量库切换能力测试

验证统一接口层：
    - 三种后端类（Chroma/pgvector/Milvus）都实现统一接口
    - 工厂函数根据配置正确选择后端
    - 非法类型正确报错
    - 配置项正确读取

不实际连接后端服务（pgvector/Milvus 需外部服务），只验证代码结构。
"""
import sys
from pathlib import Path

# 确保能导入 rag 包（项目根目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from rag.vectorstore import (
    BaseVectorStore,
    ChromaStore,
    PgVectorStore,
    MilvusStore,
    get_vectorstore,
)
from rag.config import VECTOR_STORE_TYPE, PGVECTOR_URL, MILVUS_HOST, MILVUS_PORT


# ============================================================
# 统一接口定义
# ============================================================
class TestInterfaceContract:
    """所有后端都应实现统一接口方法。"""

    @pytest.mark.parametrize("cls", [ChromaStore, PgVectorStore, MilvusStore])
    def test_implements_base(self, cls):
        assert issubclass(cls, BaseVectorStore)

    @pytest.mark.parametrize("cls", [ChromaStore, PgVectorStore, MilvusStore])
    def test_has_required_methods(self, cls):
        """应实现 add/upsert/update/delete/get/similarity_search。"""
        for method in [
            "add", "upsert", "update", "delete", "get",
            "similarity_search_with_relevance_scores",
        ]:
            assert hasattr(cls, method), f"{cls.__name__} 缺少 {method}"


# ============================================================
# 工厂函数
# ============================================================
class TestFactory:
    def test_default_is_chroma(self):
        """默认应使用 chroma 后端。"""
        assert VECTOR_STORE_TYPE == "chroma"

    def test_returns_chroma_store(self):
        """chroma 类型应返回 ChromaStore。"""
        store = get_vectorstore()
        assert isinstance(store, ChromaStore)

    def test_invalid_type_raises(self, monkeypatch):
        """非法类型应抛出 ValueError。"""
        monkeypatch.setattr("rag.vectorstore.VECTOR_STORE_TYPE", "invalid")
        with pytest.raises(ValueError):
            get_vectorstore()


# ============================================================
# 配置项
# ============================================================
class TestConfig:
    def test_pgvector_url_configured(self):
        assert PGVECTOR_URL.startswith("postgresql")

    def test_milvus_config_configured(self):
        assert isinstance(MILVUS_PORT, int)
        assert isinstance(MILVUS_HOST, str)
