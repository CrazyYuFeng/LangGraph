"""rag/cache.py —— 分层缓存系统

四种缓存层：
    1. 瞬时缓存（instant）：内存，秒级 TTL，会话上下文
    2. 短缓存（short）：Redis，分钟级 TTL，实时数据查询
    3. 长缓存（long）：Redis，小时级 TTL，知识库问答
    4. 偏好缓存（preference）：Redis，永久，用户偏好

缓存选择逻辑：根据查询类型自动选择缓存层。
"""
import hashlib
import time
from typing import Optional

import redis

from rag.config import REDIS_URL
from rag.logging_setup import get_logger

logger = get_logger(__name__)


class InstantCache:
    """瞬时缓存：内存存储，秒级 TTL，会话结束即清。"""

    def __init__(self, ttl: int = 300):
        self.ttl = ttl  # 默认 5 分钟
        self._cache = {}  # key -> (value, expire_time)

    def _make_key(self, query: str) -> str:
        return "".join(query.split()).lower()

    def get(self, query: str) -> Optional[str]:
        key = self._make_key(query)
        entry = self._cache.get(key)
        if not entry:
            return None
        value, expire = entry
        if time.time() > expire:
            del self._cache[key]
            return None
        return value

    def set(self, query: str, value: str):
        key = self._make_key(query)
        self._cache[key] = (value, time.time() + self.ttl)

    def clear(self):
        self._cache.clear()


class RedisCache:
    """Redis 缓存基类：短缓存、长缓存、偏好缓存共用。"""

    def __init__(self, ttl: int, prefix: str):
        self.ttl = ttl
        self.prefix = prefix
        self._client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    def _make_key(self, query: str) -> str:
        normalized = "".join(query.split()).lower()
        return self.prefix + hashlib.md5(normalized.encode()).hexdigest()

    def get(self, query: str) -> Optional[str]:
        try:
            return self._client.get(self._make_key(query))
        except redis.RedisError as e:
            logger.error("Redis 读取失败: %s", e)
            return None

    def set(self, query: str, value: str, ttl: int = None):
        try:
            self._client.set(self._make_key(query), value, ex=ttl or self.ttl)
        except redis.RedisError as e:
            logger.error("Redis 写入失败: %s", e)

    def clear(self):
        try:
            keys = self._client.keys(self.prefix + "*")
            if keys:
                self._client.delete(*keys)
        except redis.RedisError as e:
            logger.error("Redis 清空失败: %s", e)

    def size(self) -> int:
        try:
            return len(self._client.keys(self.prefix + "*"))
        except redis.RedisError:
            return 0


class PreferenceCache(RedisCache):
    """偏好缓存：永久存储，用户更新偏好时清空。"""

    def __init__(self, prefix: str = "rag_pref:"):
        super().__init__(ttl=None, prefix=prefix)  # ttl=None 表示永久

    def set(self, query: str, value: str, ttl: int = None):
        """偏好缓存永久存储（不设 TTL）。"""
        try:
            self._client.set(self._make_key(query), value)
        except redis.RedisError as e:
            logger.error("偏好缓存写入失败: %s", e)


# ============================================================
# 缓存层实例
# ============================================================
instant_cache = InstantCache(ttl=300)      # 瞬时：5 分钟，内存
short_cache = RedisCache(ttl=1800, prefix="rag_short:")     # 短：30 分钟，Redis
long_cache = RedisCache(ttl=86400, prefix="rag_long:")      # 长：24 小时，Redis
preference_cache = PreferenceCache()                        # 偏好：永久，Redis


# ============================================================
# 缓存选择逻辑
# ============================================================
def classify_query(query: str) -> str:
    """根据查询类型判断用哪层缓存。

    返回: "instant" / "short" / "long" / "preference" / "none"
    """
    q = query.lower()

    # 偏好缓存：用户明确表达偏好/设置
    if any(k in q for k in ["我偏好", "我的设置", "我喜欢", "记住我", "偏好", "默认"]):
        return "preference"

    # 长缓存：知识库问答（业务规则、说明、定义）—— 优先于实时数据
    # 含"表示/是什么/说明/规则"等明确是知识问答
    if any(k in q for k in ["表示", "是什么", "说明", "规则", "定义", "含义", "介绍", "区别"]):
        return "long"

    # 短缓存：实时数据查询（金额、订单、统计等实时数据）
    if any(k in q for k in ["当前", "最新", "实时", "现在", "统计", "金额", "订单", "多少", "几条"]):
        return "short"

    # 瞬时缓存：会话上下文、简单问候
    if any(k in q for k in ["你好", "hi", "hello", "继续", "再说"]):
        return "instant"

    return "none"


# 缓存层映射
_CACHE_LAYERS = {
    "instant": instant_cache,
    "short": short_cache,
    "long": long_cache,
    "preference": preference_cache,
}


def get_cached(query: str) -> Optional[str]:
    """按查询类型查缓存。"""
    level = classify_query(query)
    if level == "none":
        return None
    cache = _CACHE_LAYERS.get(level)
    if cache:
        result = cache.get(query)
        if result:
            logger.debug("命中%s缓存", level)
        return result
    return None


def set_cached(query: str, answer: str):
    """按查询类型写缓存。"""
    level = classify_query(query)
    if level == "none":
        return
    cache = _CACHE_LAYERS.get(level)
    if cache:
        cache.set(query, answer)


def clear_all_cache():
    """清空所有缓存（增量更新时调用）。"""
    instant_cache.clear()
    short_cache.clear()
    long_cache.clear()
    # 偏好缓存不清（用户偏好不随数据更新失效）
    logger.info("已清空瞬时/短/长缓存（偏好缓存保留）")


# 兼容旧的 query_cache 接口（供 rag_chain 使用）
class _QueryCacheCompat:
    """兼容层：把分层缓存封装成统一的 query_cache 接口。"""

    def get(self, query: str) -> Optional[str]:
        return get_cached(query)

    def set(self, query: str, answer: str):
        set_cached(query, answer)

    def clear(self):
        clear_all_cache()


query_cache = _QueryCacheCompat()
