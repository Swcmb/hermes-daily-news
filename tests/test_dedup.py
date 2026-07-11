# test_dedup.py — 去重单元测试
import pytest
from lib.dedup import dedup, _normalize_url, _title_hash


class TestNormalizeUrl:
    """URL 归一化"""

    def test_strip_utm_params(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social&id=123"
        normalized = _normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized
        assert "id=123" in normalized

    def test_strip_fbclid(self):
        url = "https://example.com/a?fbclid=abc123&keep=this"
        normalized = _normalize_url(url)
        assert "fbclid" not in normalized
        assert "keep=this" in normalized

    def test_empty_url(self):
        assert _normalize_url("") == ""

    def test_invalid_url(self):
        assert _normalize_url("not a url") == ""


class TestTitleHash:
    """标题 hash"""

    def test_same_title_same_hash(self):
        assert _title_hash("Hello World") == _title_hash("Hello World")

    def test_different_order_same_hash(self):
        # 分词排序后应相同
        h1 = _title_hash("Machine Learning Advanced")
        h2 = _title_hash("Advanced Learning Machine")
        assert h1 == h2

    def test_case_insensitive(self):
        assert _title_hash("Hello") == _title_hash("HELLO")

    def test_punctuation_ignored(self):
        h1 = _title_hash("Hello, World!")
        h2 = _title_hash("Hello World")
        assert h1 == h2

    def test_empty_title(self):
        assert _title_hash("") == ""


class TestDedup:
    """跨源去重"""

    def test_url_dedup_across_sources(self):
        results = [
            {"source": "arxiv_cs_ai", "status": "ok", "item_count": 2, "items": [
                {"title": "Paper A", "url": "https://arxiv.org/abs/2026.111"},
                {"title": "Paper B", "url": "https://arxiv.org/abs/2026.222"},
            ]},
            {"source": "arxiv_cs_lg", "status": "ok", "item_count": 2, "items": [
                {"title": "Paper C", "url": "https://arxiv.org/abs/2026.111"},  # URL 重复
                {"title": "Paper D", "url": "https://arxiv.org/abs/2026.333"},
            ]},
        ]
        out = dedup(results)
        # arxiv_cs_ai 优先,保留 2 条;arxiv_cs_lg 去重后保留 1 条
        assert out[0]["item_count"] == 2
        assert out[1]["item_count"] == 1
        assert out[1]["items"][0]["title"] == "Paper D"

    def test_title_hash_dedup(self):
        results = [
            {"source": "arxiv_cs_ai", "status": "ok", "item_count": 1, "items": [
                {"title": "Machine Learning Advanced", "url": "https://arxiv.org/abs/001"},
            ]},
            {"source": "arxiv_cs_lg", "status": "ok", "item_count": 1, "items": [
                {"title": "Advanced Learning Machine", "url": "https://arxiv.org/abs/002"},
                # URL 不同但标题 hash 相同
            ]},
        ]
        out = dedup(results)
        assert out[1]["item_count"] == 0  # 被去重

    def test_item_count_synced(self):
        results = [
            {"source": "arxiv_cs_ai", "status": "ok", "item_count": 3, "items": [
                {"title": "A", "url": "https://a.com/1"},
                {"title": "B", "url": "https://a.com/2"},
                {"title": "C", "url": "https://a.com/3"},
            ]},
            {"source": "zhihu", "status": "ok", "item_count": 2, "items": [
                {"title": "A2", "url": "https://a.com/1"},  # URL 重复
                {"title": "D", "url": "https://a.com/4"},
            ]},
        ]
        out = dedup(results)
        # 找到 zhihu 的结果
        zhihu = next(r for r in out if r["source"] == "zhihu")
        assert zhihu["item_count"] == 1
        assert zhihu["items"][0]["title"] == "D"

    def test_failed_source_skipped(self):
        results = [
            {"source": "arxiv_cs_ai", "status": "fail", "item_count": 0, "items": []},
            {"source": "zhihu", "status": "ok", "item_count": 1, "items": [
                {"title": "A", "url": "https://a.com/1"},
            ]},
        ]
        out = dedup(results)
        zhihu = next(r for r in out if r["source"] == "zhihu")
        assert zhihu["item_count"] == 1  # 不受 fail 源影响

    def test_source_priority_order(self):
        # zhihu 在 arxiv_cs_ai 之后(优先级低)
        results = [
            {"source": "zhihu", "status": "ok", "item_count": 1, "items": [
                {"title": "Same", "url": "https://same.com/1"},
            ]},
            {"source": "arxiv_cs_ai", "status": "ok", "item_count": 1, "items": [
                {"title": "Same2", "url": "https://same.com/1"},  # URL 重复
            ]},
        ]
        out = dedup(results)
        # arxiv_cs_ai 优先级高,应保留;zhihu 被去重
        arxiv = next(r for r in out if r["source"] == "arxiv_cs_ai")
        zhihu = next(r for r in out if r["source"] == "zhihu")
        assert arxiv["item_count"] == 1
        assert zhihu["item_count"] == 0
