# test_arxiv_parser.py — arXiv RSS 解析器单元测试
import pytest
from lib.parsers.arxiv_parser import parse


# ===== 测试 fixtures =====

ARXIV_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>arXiv: cs.AI</title>
<item>
<title><![CDATA[Multi-Agent Reinforcement Learning for Robotics]]></title>
<link>https://arxiv.org/abs/2026.12345</link>
<description><![CDATA[arXiv:2026.12345 Announce Type: cross
Abstract: We propose a novel framework for multi-agent RL.]]></description>
</item>
<item>
<title><![CDATA[Transformer-Based Language Models]]></title>
<link>https://arxiv.org/abs/2026.67890</link>
<description><![CDATA[arXiv:2026.67890 Announce Type: new
Abstract: This paper introduces improvements to transformer architectures.]]></description>
</item>
</channel>
</rss>"""

ARXIV_EMPTY = "<rss></rss>"


# ===== 测试用例 =====

class TestArxivParserBasic:
    """基础解析功能"""

    def test_parse_arxiv_rss(self):
        items = parse(ARXIV_RSS, limit=6)
        assert len(items) == 2
        assert "Multi-Agent" in items[0]["title"]

    def test_arxiv_id_extracted(self):
        items = parse(ARXIV_RSS)
        assert items[0]["meta"]["arxiv_id"] == "2026.12345"
        assert items[1]["meta"]["arxiv_id"] == "2026.67890"

    def test_lang_marker(self):
        items = parse(ARXIV_RSS)
        assert items[0]["meta"]["lang"] == "en"

    def test_limit_respected(self):
        items = parse(ARXIV_RSS, limit=1)
        assert len(items) == 1


class TestArxivParserAbstract:
    """abstract 清洗"""

    def test_arxiv_prefix_removed(self):
        items = parse(ARXIV_RSS)
        # "arXiv:xxx Announce Type: xxx Abstract:" 前缀应被去除
        assert "arXiv:" not in items[0]["abstract"]
        assert "Announce Type" not in items[0]["abstract"]
        assert "Abstract:" not in items[0]["abstract"]

    def test_abstract_content_preserved(self):
        items = parse(ARXIV_RSS)
        assert "multi-agent RL" in items[0]["abstract"]

    def test_link_is_valid_url(self):
        items = parse(ARXIV_RSS)
        assert items[0]["url"] == "https://arxiv.org/abs/2026.12345"


class TestArxivParserEdgeCases:
    """边界条件"""

    def test_empty_content(self):
        assert parse("") == []

    def test_short_content(self):
        assert parse("<rss></rss>") == []

    def test_item_without_link(self):
        # arXiv 阈值 500 字符,需构造足够长的输入
        rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>arXiv: cs.AI recent submissions</title>
<description>arXiv.org RSS feed for cs.AI - This feed contains recent submissions to the cs.AI category</description>
<item>
<title><![CDATA[无链接论文:A Study on Graph Neural Networks for Molecular Property Prediction in Drug Discovery Applications]]></title>
<description><![CDATA[arXiv:2026.99999 Announce Type: new Abstract: We study Graph Neural Networks (GNNs) for molecular property prediction tasks in drug discovery. Our framework leverages message passing neural networks to learn molecular representations from graph-structured data, achieving state-of-the-art results on multiple benchmark datasets including MoleculeNet and Tox21.]]></description>
</item>
</channel></rss>"""
        items = parse(rss)
        assert len(items) == 1
        assert items[0]["meta"]["arxiv_id"] == ""

    def test_cdata_unwrapped(self):
        items = parse(ARXIV_RSS)
        # CDATA 应被解包,标题不含 CDATA 标记
        assert "<![CDATA[" not in items[0]["title"]
