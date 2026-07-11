# test_cache.py — 文件缓存单元测试
import json
import os
import time
import tempfile
import pytest
from lib import cache


@pytest.fixture
def temp_cache_dir(monkeypatch):
    """使用临时目录作为缓存目录,测试后自动清理。"""
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("CACHE_DIR", d)
        yield d


class TestCacheGetSet:
    """缓存读写"""

    def test_set_and_get(self, temp_cache_dir):
        url = "https://example.com/feed"
        data = {"source": "test", "items": [{"title": "hello"}]}
        cache.set_cache(url, data)
        result = cache.get_cache(url, ttl=3600)
        assert result is not None
        assert result["source"] == "test"
        assert result["items"][0]["title"] == "hello"

    def test_miss_on_nonexistent(self, temp_cache_dir):
        result = cache.get_cache("https://example.com/not-cached", ttl=3600)
        assert result is None

    def test_atomic_write_no_tmp_left(self, temp_cache_dir):
        url = "https://example.com/atomic"
        cache.set_cache(url, {"data": 1})
        # .tmp 文件不应残留
        files = os.listdir(temp_cache_dir)
        assert not any(f.endswith(".tmp") for f in files)


class TestCacheTTL:
    """TTL 过期"""

    def test_expired_cache_returns_none(self, temp_cache_dir):
        url = "https://example.com/expired"
        cache.set_cache(url, {"data": 1})
        # 手动将文件时间回拨 2 小时前
        import glob
        key = cache._cache_key(url)
        path = os.path.join(temp_cache_dir, key)
        old_time = time.time() - 7200
        os.utime(path, (old_time, old_time))
        # TTL=3600(1h),文件已过期 2h,应返回 None
        assert cache.get_cache(url, ttl=3600) is None

    def test_fresh_cache_returns_data(self, temp_cache_dir):
        url = "https://example.com/fresh"
        cache.set_cache(url, {"data": 1})
        # 刚写入,TTL=3600 应命中
        assert cache.get_cache(url, ttl=3600) is not None


class TestCacheClear:
    """清理机制"""

    def test_clear_expired_removes_old_files(self, temp_cache_dir):
        # 写入两个缓存,一个过期一个不过期
        cache.set_cache("https://example.com/old", {"d": 1})
        cache.set_cache("https://example.com/new", {"d": 2})
        # 回拨 old 的时间
        old_path = os.path.join(temp_cache_dir, cache._cache_key("https://example.com/old"))
        old_time = time.time() - 72000  # 20h 前
        os.utime(old_path, (old_time, old_time))
        # 清理 48h 以上的(20h 不会被清理)
        count = cache.clear_expired(temp_cache_dir, retention_hours=48)
        assert count == 0
        # 清理 10h 以上的(20h 会被清理)
        count = cache.clear_expired(temp_cache_dir, retention_hours=10)
        assert count == 1

    def test_clear_done_markers(self, tmp_path):
        # 创建 .done 标记文件
        import glob
        marker1 = "/tmp/news-tech-ai-test1.done"
        marker2 = "/tmp/news-tech-ai-test2.done"
        for m in (marker1, marker2):
            with open(m, "w") as f:
                f.write("")
        # 回拨 marker1 的时间
        old_time = time.time() - 72000  # 20h 前
        os.utime(marker1, (old_time, old_time))
        # 清理 10h 以上的(只有 marker1 符合)
        count = cache.clear_done_markers(retention_hours=10)
        assert count >= 1
        assert not os.path.exists(marker1)
        assert os.path.exists(marker2)
        # 清理临时标记
        if os.path.exists(marker2):
            os.unlink(marker2)


class TestCacheSourceName:
    """source_name 隔离:同 URL 不同 parser 的缓存应独立"""

    def test_same_url_different_source_independent(self, temp_cache_dir):
        """同 URL 不同 source_name 应写入不同缓存文件,互不干扰。"""
        url = "https://example.com/shared-feed"
        # 模拟 36kr 被 comprehensive(rss) 和 tech-ai(news_filter) 共用
        cache.set_cache(url, {"items": ["rss-data"]}, source_name="36kr")
        cache.set_cache(url, {"items": ["news_filter-data"]}, source_name="kr_ai")
        # 读取时应各自命中独立缓存
        r1 = cache.get_cache(url, ttl=3600, source_name="36kr")
        r2 = cache.get_cache(url, ttl=3600, source_name="kr_ai")
        assert r1["items"] == ["rss-data"]
        assert r2["items"] == ["news_filter-data"]

    def test_different_cache_key(self, temp_cache_dir):
        """source_name 不同时,_cache_key 应不同。"""
        url = "https://example.com/feed"
        key1 = cache._cache_key(url, source_name="36kr")
        key2 = cache._cache_key(url, source_name="kr_ai")
        key3 = cache._cache_key(url)  # 不传 source_name(向后兼容)
        assert key1 != key2
        # 不传 source_name 时退化为仅 URL 哈希,与传入不同
        assert key3 != key1
        assert key3 != key2

    def test_backward_compat_no_source_name(self, temp_cache_dir):
        """不传 source_name 时应退化为旧行为(仅按 URL 哈希)。"""
        url = "https://example.com/legacy"
        # 旧式调用(无 source_name)写入
        cache.set_cache(url, {"data": "legacy"})
        # 旧式读取应命中
        result = cache.get_cache(url, ttl=3600)
        assert result is not None
        assert result["data"] == "legacy"

    def test_source_name_isolation_not_polluted(self, temp_cache_dir):
        """验证 news_filter 缓存不会被 rss 缓存污染。"""
        url = "https://rsshub.rssforever.com/36kr/newsflashes"
        # comprehensive 用 rss parser 写入 20 条
        cache.set_cache(url, {"items": [{"i": i} for i in range(20)]}, source_name="36kr")
        # tech-ai 用 news_filter 写入 5 条(过滤后)
        cache.set_cache(url, {"items": [{"i": i} for i in range(5)]}, source_name="kr_ai")
        # 读取 36kr 缓存应仍是 20 条,不被 news_filter 的 5 条覆盖
        r_36kr = cache.get_cache(url, ttl=3600, source_name="36kr")
        r_kr_ai = cache.get_cache(url, ttl=3600, source_name="kr_ai")
        assert len(r_36kr["items"]) == 20
        assert len(r_kr_ai["items"]) == 5
