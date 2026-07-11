# test_hn_parser.py — Hacker News Algolia API 解析器单元测试
import json
import pytest
from lib.parsers.hn_parser import parse


HN_JSON = json.dumps({
    "hits": [
        {
            "title": "Show HN: A new framework for LLM agents",
            "url": "https://github.com/user/agent-fw",
            "points": 342,
            "num_comments": 56,
            "objectID": "123456"
        },
        {
            "title": "Research: Scaling laws for mixture of experts",
            "url": "https://arxiv.org/abs/2026.12345",
            "points": 189,
            "num_comments": 23,
            "objectID": "123457"
        },
        {
            "story_title": "Discussion: Future of AI",
            "story_url": "https://news.ycombinator.com/item?id=123",
            "points": 50,
            "num_comments": 10,
            "objectID": "123458"
        }
    ]
})

HN_EMPTY = json.dumps({"hits": []})
INVALID_JSON = "not json"


class TestHnParserBasic:
    def test_parse_hn_json(self):
        items = parse(HN_JSON, limit=10)
        assert len(items) == 3
        assert "LLM agents" in items[0]["title"]

    def test_points_extracted(self):
        items = parse(HN_JSON)
        assert items[0]["meta"]["points"] == 342
        assert items[1]["meta"]["points"] == 189

    def test_num_comments_extracted(self):
        items = parse(HN_JSON)
        assert items[0]["meta"]["num_comments"] == 56

    def test_limit_respected(self):
        items = parse(HN_JSON, limit=2)
        assert len(items) == 2

    def test_story_title_fallback(self):
        """title 为空时用 story_title"""
        items = parse(HN_JSON)
        assert items[2]["title"] == "Discussion: Future of AI"


class TestHnParserEdgeCases:
    def test_empty_hits(self):
        assert parse(HN_EMPTY) == []

    def test_invalid_json(self):
        assert parse(INVALID_JSON) == []

    def test_empty_content(self):
        assert parse("") == []

    def test_missing_title_skipped(self):
        data = json.dumps({"hits": [{"url": "https://example.com", "points": 1}]})
        items = parse(data)
        assert items == []
