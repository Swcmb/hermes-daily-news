# test_producthunt_parser.py — Product Hunt RSS 解析器单元测试
import pytest
from lib.parsers.producthunt_parser import parse


PH_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Product Hunt</title>
<item>
<title>AI Code Assistant Pro</title>
<link>https://www.producthunt.com/posts/ai-code-assistant-pro</link>
<description>Build apps faster with AI-powered code generation</description>
</item>
<item>
<title>DataViz Toolkit</title>
<link>https://www.producthunt.com/posts/dataviz-toolkit</link>
<description>Beautiful charts in seconds ▲ 234 upvotes</description>
</item>
</channel>
</rss>"""

EMPTY_RSS = ""
SHORT_RSS = "<rss></rss>"


class TestProductHuntParserBasic:
    def test_parse_ph_rss(self):
        items = parse(PH_RSS, limit=6)
        assert len(items) == 2
        assert items[0]["title"] == "AI Code Assistant Pro"

    def test_url_extracted(self):
        items = parse(PH_RSS)
        assert items[0]["url"] == "https://www.producthunt.com/posts/ai-code-assistant-pro"

    def test_limit_respected(self):
        items = parse(PH_RSS, limit=1)
        assert len(items) == 1

    def test_empty_content(self):
        assert parse(EMPTY_RSS) == []

    def test_short_content(self):
        assert parse(SHORT_RSS) == []


class TestProductHuntVotes:
    def test_votes_extracted(self):
        items = parse(PH_RSS)
        assert items[1]["meta"]["votes"] == "234"

    def test_no_votes_empty(self):
        items = parse(PH_RSS)
        assert items[0]["meta"]["votes"] == ""
