# test_reddit_parser.py — Reddit JSON 解析器单元测试
import json
import pytest
from lib.parsers.reddit_parser import parse


REDDIT_JSON = json.dumps({
    "data": {
        "children": [
            {
                "data": {
                    "title": "[D] Discussion about GPT-5 capabilities",
                    "url": "https://arxiv.org/abs/2026.12345",
                    "permalink": "/r/MachineLearning/comments/abc123/discussion_about_gpt5/",
                    "score": 456,
                    "num_comments": 78
                }
            },
            {
                "data": {
                    "title": "[R] New transformer architecture paper",
                    "url": "https://example.com/paper",
                    "permalink": "/r/MachineLearning/comments/def456/new_transformer/",
                    "score": 234,
                    "num_comments": 45
                }
            }
        ]
    }
})

REDDIT_EMPTY = json.dumps({"data": {"children": []}})
INVALID_JSON = "not json"


class TestRedditParserBasic:
    def test_parse_reddit_json(self):
        items = parse(REDDIT_JSON, limit=6)
        assert len(items) == 2
        assert "GPT-5" in items[0]["title"]

    def test_score_extracted(self):
        items = parse(REDDIT_JSON)
        assert items[0]["meta"]["score"] == 456

    def test_permalink_to_full_url(self):
        items = parse(REDDIT_JSON)
        assert items[0]["url"] == "https://www.reddit.com/r/MachineLearning/comments/abc123/discussion_about_gpt5/"

    def test_limit_respected(self):
        items = parse(REDDIT_JSON, limit=1)
        assert len(items) == 1


class TestRedditParserEdgeCases:
    def test_empty_children(self):
        assert parse(REDDIT_EMPTY) == []

    def test_invalid_json(self):
        assert parse(INVALID_JSON) == []

    def test_empty_content(self):
        assert parse("") == []

    def test_missing_title_skipped(self):
        data = json.dumps({"data": {"children": [{"data": {"score": 1}}]}})
        items = parse(data)
        assert items == []
