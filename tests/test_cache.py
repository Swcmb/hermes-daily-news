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
