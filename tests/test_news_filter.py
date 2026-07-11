# test_news_filter.py — news_filter parser(AI 关键词过滤)单元测试
import pytest
from lib.parsers.news_filter import parse, DEFAULT_AI_KEYWORDS

# 含 AI 相关与不相关条目的 RSS 样本
RSS_MIXED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>36氪快讯</title>
<description>科技商业资讯</description>
<item>
<title>OpenAI 发布 GPT-5 新模型</title>
<link>https://36kr.com/p/1</link>
<description>OpenAI 今日发布 GPT-5,性能大幅提升</description>
</item>
<item>
<title>某公司获得 A 轮融资</title>
<link>https://36kr.com/p/2</link>
<description>AI 芯片创业公司完成 5 亿元融资</description>
</item>
<item>
<title>今日天气晴朗</title>
<link>https://36kr.com/p/3</link>
<description>全国大部分地区天气良好</description>
</item>
<item>
<title>大模型推理优化新进展</title>
<link>https://36kr.com/p/4</link>
<description>LLM 推理速度提升 3 倍</description>
</item>
<item>
<title>房地产市场动态</title>
<link>https://36kr.com/p/5</link>
<description>一线城市房价走势分析</description>
</item>
<item>
<title>Anthropic 推出 Claude 4</title>
<link>https://36kr.com/p/6</link>
<description>Anthropic 发布新一代 AI 助手</description>
</item>
</channel>
</rss>"""

# 全部不相关条目
RSS_NO_AI = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>生活资讯</title>
<item>
<title>今日菜价稳中有降</title>
<link>https://example.com/1</link>
<description>蔬菜价格走势平稳</description>
</item>
<item>
<title>周末交通出行提示</title>
<link>https://example.com/2</link>
<description>高速公路车流量预计增大</description>
</item>
</channel>
</rss>"""

# 空内容
RSS_EMPTY = """<?xml version="1.0"?>
<rss version="2.0"><channel></channel></rss>"""


class TestNewsFilterBasic:
    """基础过滤功能测试"""

    def test_filters_ai_related_items(self):
        """验证 AI 相关条目被保留"""
        results = parse(RSS_MIXED, limit=6)
        titles = [item["title"] for item in results]
        # 应包含 AI 相关条目
        assert "OpenAI 发布 GPT-5 新模型" in titles
        assert "某公司获得 A 轮融资" in titles
        assert "大模型推理优化新进展" in titles
        assert "Anthropic 推出 Claude 4" in titles

    def test_excludes_non_ai_items(self):
        """验证非 AI 条目被过滤"""
        results = parse(RSS_MIXED, limit=6)
        titles = [item["title"] for item in results]
        # 不应包含非 AI 条目
        assert "今日天气晴朗" not in titles
        assert "房地产市场动态" not in titles

    def test_limit_respected(self):
        """验证 limit 限制生效"""
        results = parse(RSS_MIXED, limit=2)
        assert len(results) == 2

    def test_returns_empty_for_no_ai_content(self):
        """无 AI 相关条目时返回空列表"""
        results = parse(RSS_NO_AI, limit=6)
        assert results == []

    def test_returns_empty_for_empty_content(self):
        """空 RSS 返回空列表"""
        results = parse(RSS_EMPTY, limit=6)
        assert results == []


class TestNewsFilterKeywords:
    """关键词传递机制测试"""

    def test_custom_keywords_used(self):
        """验证自定义 keywords 生效"""
        # 用"菜价""交通"匹配 RSS_NO_AI 中的条目
        results = parse(RSS_NO_AI, limit=6, keywords=["菜价", "交通"])
        titles = [item["title"] for item in results]
        assert "今日菜价稳中有降" in titles
        assert "周末交通出行提示" in titles

    def test_default_keywords_when_none(self):
        """keywords=None 时使用 DEFAULT_AI_KEYWORDS"""
        results = parse(RSS_MIXED, limit=6, keywords=None)
        assert len(results) > 0
        # 验证确实用了 AI 关键词(OpenAI 命中)
        titles = [item["title"] for item in results]
        assert any("OpenAI" in t or "GPT" in t for t in titles)

    def test_keyword_match_in_abstract(self):
        """关键词在摘要中命中也应保留"""
        # "AI 芯片创业公司完成 5 亿元融资" 标题无关键词,但摘要有"AI""芯片""融资"
        results = parse(RSS_MIXED, limit=6, keywords=["芯片"])
        titles = [item["title"] for item in results]
        assert "某公司获得 A 轮融资" in titles

    def test_default_keywords_list_not_empty(self):
        """DEFAULT_AI_KEYWORDS 非空"""
        assert len(DEFAULT_AI_KEYWORDS) > 0
        assert "AI" in DEFAULT_AI_KEYWORDS


class TestNewsFilterEdgeCases:
    """边界条件测试"""

    def test_empty_string_input(self):
        """空字符串输入返回空列表"""
        assert parse("", limit=6) == []

    def test_short_content_rejected(self):
        """过短内容(<100字符)返回空列表"""
        short = "<rss></rss>"
        assert parse(short, limit=6) == []

    def test_limit_zero(self):
        """limit=0 返回空列表"""
        results = parse(RSS_MIXED, limit=0)
        assert results == []

    def test_keywords_empty_list(self):
        """空关键词列表返回空(无法匹配)"""
        results = parse(RSS_MIXED, limit=6, keywords=[])
        # 空列表时 any() 对空可迭代对象返回 False,所有条目都不命中
        assert results == []
