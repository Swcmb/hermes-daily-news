# test_github_parser.py — GitHub Search API JSON 解析器单元测试
import json
import pytest
from lib.parsers.github_parser import parse


# ===== 测试 fixtures =====

GITHUB_JSON = json.dumps({
    "total_count": 2,
    "items": [
        {
            "full_name": "user/awesome-llm",
            "html_url": "https://github.com/user/awesome-llm",
            "description": "A curated list of LLM resources",
            "stargazers_count": 1234,
            "language": "Python"
        },
        {
            "full_name": "user/agent-framework",
            "html_url": "https://github.com/user/agent-framework",
            "description": "Build AI agents with\nmulti-line description",
            "stargazers_count": 567,
            "language": "TypeScript"
        }
    ]
})

GITHUB_EMPTY = json.dumps({"total_count": 0, "items": []})

GITHUB_MISSING_FIELDS = json.dumps({
    "items": [
        {"full_name": "user/minimal"},
        {"full_name": "", "html_url": "https://github.com/empty"}
    ]
})

INVALID_JSON = "not a json string"


# ===== 测试用例 =====

class TestGithubParserBasic:
    """基础解析功能"""

    def test_parse_github_json(self):
        items = parse(GITHUB_JSON, limit=8)
        assert len(items) == 2
        assert items[0]["title"] == "user/awesome-llm"
        assert items[0]["url"] == "https://github.com/user/awesome-llm"

    def test_stars_extracted(self):
        items = parse(GITHUB_JSON)
        assert items[0]["meta"]["stars"] == 1234
        assert items[1]["meta"]["stars"] == 567

    def test_language_extracted(self):
        items = parse(GITHUB_JSON)
        assert items[0]["meta"]["language"] == "Python"
        assert items[1]["meta"]["language"] == "TypeScript"

    def test_limit_respected(self):
        items = parse(GITHUB_JSON, limit=1)
        assert len(items) == 1


class TestGithubParserEdgeCases:
    """边界条件"""

    def test_empty_items(self):
        items = parse(GITHUB_EMPTY)
        assert items == []

    def test_invalid_json(self):
        items = parse(INVALID_JSON)
        assert items == []

    def test_missing_fields(self):
        items = parse(GITHUB_MISSING_FIELDS)
        # 第一个 repo 有 full_name,应被解析
        assert len(items) == 1
        assert items[0]["title"] == "user/minimal"
        # 缺失字段应有默认值
        assert items[0]["meta"]["stars"] == 0
        assert items[0]["meta"]["language"] == ""

    def test_empty_content(self):
        assert parse("") == []


class TestGithubParserSecurity:
    """内容安全"""

    def test_multiline_description_compressed(self):
        items = parse(GITHUB_JSON)
        # 换行应被压缩为空格
        assert "\n" not in items[1]["abstract"]
        assert "multi-line description" in items[1]["abstract"]
