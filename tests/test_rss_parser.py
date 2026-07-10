# test_rss_parser.py — RSS 通用解析器单元测试
import pytest
from lib.parsers.rss_parser import parse


# ===== 测试 fixtures =====

SIMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>测试源</title>
<item>
<title>第一条新闻</title>
<link>https://example.com/news/1</link>
<description>这是第一条新闻的描述</description>
</item>
<item>
<title>第二条新闻</title>
<link>https://example.com/news/2</link>
<description>这是第二条新闻的描述</description>
</item>
</channel>
</rss>"""

RSS_WITH_CDATA = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
<title><![CDATA[CDATA 标题测试]]></title>
<link><![CDATA[https://example.com/cdata]]></link>
<description><![CDATA[<p>含 HTML 的描述</p>]]></description>
</item>
</channel></rss>"""

RSS_WITH_XSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
<title>正常标题</title>
<link>javascript:alert(1)</link>
<description><script>alert('xss')</script>描述内容</description>
</item>
</channel></rss>"""

EMPTY_RSS = ""
SHORT_RSS = "<rss></rss>"


# ===== 测试用例 =====

class TestRssParserBasic:
    """基础解析功能"""

    def test_parse_simple_rss(self):
        items = parse(SIMPLE_RSS, limit=10)
        assert len(items) == 2
        assert items[0]["title"] == "第一条新闻"
        assert items[0]["url"] == "https://example.com/news/1"
        assert items[0]["abstract"] == "这是第一条新闻的描述"

    def test_limit_respected(self):
        items = parse(SIMPLE_RSS, limit=1)
        assert len(items) == 1

    def test_empty_content(self):
        assert parse(EMPTY_RSS) == []

    def test_short_content(self):
        assert parse(SHORT_RSS) == []


class TestRssParserCData:
    """CDATA 解包"""

    def test_cdata_unwrapped(self):
        items = parse(RSS_WITH_CDATA)
        assert len(items) == 1
        assert "CDATA" in items[0]["title"]
        assert items[0]["url"] == "https://example.com/cdata"

    def test_html_in_description_stripped(self):
        items = parse(RSS_WITH_CDATA)
        # HTML 标签应被剥离
        assert "<p>" not in items[0]["abstract"]
        assert "含 HTML 的描述" in items[0]["abstract"]


class TestRssParserSecurity:
    """内容安全清洗"""

    def test_javascript_url_rejected(self):
        items = parse(RSS_WITH_XSS)
        assert len(items) == 1
        # javascript: 协议应被拒绝,url 为空
        assert items[0]["url"] == ""

    def test_script_tag_stripped(self):
        items = parse(RSS_WITH_XSS)
        # <script> 标签应被剥离,标签内的文本内容保留(sanitize 只剥离标签不删文本)
        assert "<script>" not in items[0]["abstract"]
        assert "描述内容" in items[0]["abstract"]


class TestRssParserEdgeCases:
    """边界条件"""

    def test_missing_link(self):
        rss = '<rss version="2.0"><channel><title>测试源名称</title><item><title>无链接</title><description>描述</description></item></channel></rss>'
        items = parse(rss)
        assert len(items) == 1
        assert items[0]["url"] == ""

    def test_missing_description(self):
        rss = '<rss version="2.0"><channel><title>测试源名称</title><item><title>无描述</title><link>https://example.com</link></item></channel></rss>'
        items = parse(rss)
        assert len(items) == 1
        assert items[0]["abstract"] == ""

    def test_no_items(self):
        rss = '<rss><channel><title>无条目源</title></channel></rss>'
        items = parse(rss)
        assert items == []
