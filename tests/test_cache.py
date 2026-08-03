"""tests/test_cache.py —— 缓存模块测试

覆盖不依赖 Redis 的纯逻辑：
    - InstantCache（内存缓存）的 get/set/过期/清空
    - classify_query（查询分类逻辑）
    - 缓存 key 规范化（去空格、小写）
"""
import sys
import os
import time
from pathlib import Path

# 确保能导入 rag 包（项目根目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from rag.cache import InstantCache, classify_query


# ============================================================
# InstantCache（内存缓存）
# ============================================================
class TestInstantCache:
    def test_set_and_get(self):
        cache = InstantCache(ttl=300)
        cache.set("你好", "回复")
        assert cache.get("你好") == "回复"

    def test_key_normalization(self):
        """缓存 key 应去除空格并小写化。"""
        cache = InstantCache(ttl=300)
        cache.set("Hello World", "val")
        # "hello world" / "HELLO WORLD" 应命中同一缓存
        assert cache.get("HELLO WORLD") == "val"
        assert cache.get("hello  world") == "val"

    def test_ttl_expiry(self):
        """超过 TTL 后缓存应失效。"""
        cache = InstantCache(ttl=1)  # 1 秒过期
        cache.set("key", "value")
        assert cache.get("key") == "value"
        time.sleep(1.2)
        assert cache.get("key") is None

    def test_clear(self):
        cache = InstantCache(ttl=300)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_missing_key_returns_none(self):
        cache = InstantCache(ttl=300)
        assert cache.get("不存在的key") is None


# ============================================================
# classify_query（查询分类逻辑）
# ============================================================
class TestClassifyQuery:
    def test_preference(self):
        assert classify_query("我偏好用简洁的回答") == "preference"
        assert classify_query("记住我的设置") == "preference"

    def test_long_knowledge(self):
        assert classify_query("什么是订单状态规则") == "long"
        assert classify_query("请说明支付类型定义") == "long"

    def test_short_real_time(self):
        assert classify_query("当前订单金额是多少") == "short"
        assert classify_query("统计一下订单数量") == "short"

    def test_instant_greeting(self):
        assert classify_query("你好") == "instant"
        assert classify_query("hi") == "instant"

    def test_none(self):
        assert classify_query("随便聊聊") == "none"
        assert classify_query("") == "none"

    def test_preference_priority(self):
        """偏好表达应优先于其他分类。"""
        assert classify_query("我偏好查看订单") == "preference"
