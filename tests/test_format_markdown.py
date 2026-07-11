# test_format_markdown.py — Markdown 格式化器单元测试
import pytest
from lib.format_markdown import (
    format_markdown,
    _count_words,
    _generate_trends,
    _SOURCE_META,
    _CN_STOPWORDS,
    _EN_STOPWORDS,
)


# ===== 测试 fixtures =====

SAMPLE_RESULTS = [
    {
        "source": "zhihu",
        "status": "ok",
        "items": [
            {"title": "AI 大模型今日发布新功能", "url": "https://example.com/1", "abstract": ""},
            {"title": "OpenAI 推出 GPT-5", "url": "https://example.com/2", "abstract": ""},
        ],
    },
    {
        "source": "36kr",
        "status": "ok",
        "items": [
            {"title": "大模型赛道融资不断", "url": "https://example.com/3", "abstract": ""},
        ],
    },
    {
        "source": "weibo",
        "status": "fail",
        "error": "timeout",
        "items": [],
    },
]


# ===== _SOURCE_META 新增条目测试 =====

class TestSourceMetaNewEntries:
    """验证 kr_ai 和 techcrunch_ai 已加入 _SOURCE_META"""

    def test_kr_ai_in_meta(self):
        assert "kr_ai" in _SOURCE_META
        emoji, name, subtitle = _SOURCE_META["kr_ai"]
        assert emoji
        assert "36氪" in name or "AI" in name
        assert "{n}" in subtitle

    def test_techcrunch_ai_in_meta(self):
        assert "techcrunch_ai" in _SOURCE_META
        emoji, name, subtitle = _SOURCE_META["techcrunch_ai"]
        assert emoji
        assert "TechCrunch" in name
        assert "{n}" in subtitle

    def test_meta_count_includes_new_sources(self):
        """_SOURCE_META 应包含至少 18 个源(16 旧 + 2 新)"""
        assert len(_SOURCE_META) >= 18


# ===== _count_words 词频统计测试 =====

class TestCountWords:
    """词频统计核心逻辑"""

    def test_chinese_2char_sliding_window(self):
        """中文 2 字滑窗应正确分词"""
        freq = _count_words(["人工智能发展"])
        # 应包含"人工"、"工智"、"智能"等 2 字词
        assert "人工" in freq
        assert "智能" in freq

    def test_chinese_3char_sliding_window(self):
        """中文 3 字滑窗应正确分词"""
        freq = _count_words(["人工智能发展"])
        assert "人工智" in freq or "工智能" in freq

    def test_english_space_split(self):
        """英文按空格分词,最小长度 3"""
        freq = _count_words(["OpenAI releases GPT model"])
        assert "openai" in freq
        assert "releases" in freq
        # 2 字母词不纳入
        assert "ai" not in freq

    def test_stopwords_filtered(self):
        """停用词应被过滤"""
        freq = _count_words(["今日发布了"])
        # "今日"、"发布"、"了" 都是停用词
        assert "今日" not in freq
        assert "发布" not in freq
        assert "了" not in freq

    def test_same_word_in_same_title_counted_once(self):
        """同标题内重复词只计一次"""
        freq = _count_words(["AI AI AI 大模型 大模型"])
        assert freq.get("大模", 0) == 1
        assert freq.get("模型", 0) == 1

    def test_cross_title_accumulation(self):
        """不同标题中相同词应累加"""
        freq = _count_words(["大模型发布", "大模型融资", "大模型突破"])
        assert freq["大模"] == 3
        assert freq["模型"] == 3

    def test_empty_titles(self):
        """空标题列表应返回空 dict"""
        assert _count_words([]) == {}

    def test_mixed_cn_en(self):
        """中英混合标题应同时统计"""
        freq = _count_words(["OpenAI 大模型发布"])
        assert "openai" in freq
        assert "大模" in freq


# ===== _generate_trends 趋势生成测试 =====

class TestGenerateTrends:
    """趋势生成功能"""

    def test_trends_generated_from_results(self):
        """正常结果应生成趋势分节"""
        trends = _generate_trends(SAMPLE_RESULTS)
        assert "## 📈 今日趋势" in trends
        # "大模型" 在 zhihu 和 36kr 中各出现一次,count >= 2
        # 注意:滑窗会拆分"大模型"为"大模"和"模型"

    def test_trends_empty_when_no_repeated_words(self):
        """无重复词时应返回空字符串"""
        results = [{
            "source": "test",
            "status": "ok",
            "items": [{"title": "唯一标题词"}],
        }]
        trends = _generate_trends(results)
        assert trends == ""

    def test_trends_empty_when_all_failed(self):
        """全部源失败时应返回空字符串"""
        results = [{"source": "test", "status": "fail", "items": []}]
        trends = _generate_trends(results)
        assert trends == ""

    def test_trends_max_3_items(self):
        """趋势最多 3 条"""
        # 构造 5 个重复词的标题
        results = [{
            "source": "test",
            "status": "ok",
            "items": [
                {"title": "苹果 香蕉 橘子 葡萄 西瓜", "url": "", "abstract": ""},
                {"title": "苹果 香蕉 橘子 葡萄 西瓜", "url": "", "abstract": ""},
            ],
        }]
        trends = _generate_trends(results)
        # 统计趋势条数(以数字开头的行)
        import re
        trend_lines = re.findall(r"^\d+\. \*\*", trends, re.MULTILINE)
        assert len(trend_lines) <= 3

    def test_trends_skip_fail_sources(self):
        """失败源的标题不纳入统计"""
        results = [
            {"source": "ok_src", "status": "ok",
             "items": [{"title": "大模型", "url": "", "abstract": ""}]},
            {"source": "fail_src", "status": "fail",
             "items": [{"title": "大模型", "url": "", "abstract": ""}]},
        ]
        trends = _generate_trends(results)
        # 只有一个源成功,即使标题相同也只 count=1,不达 >= 2 阈值
        assert trends == ""


# ===== format_markdown 集成测试 =====

class TestFormatMarkdownIntegration:
    """format_markdown 端到端集成"""

    def test_comprehensive_includes_trends(self):
        """comprehensive 日报应在 footer 前包含今日趋势分节"""
        md = format_markdown(SAMPLE_RESULTS, "comprehensive")
        # 至少应包含趋势标题或无趋势时不包含(取决于词频)
        # 这里 SAMPLE_RESULTS 中"大模型"出现 2 次,应生成趋势
        assert "📈 今日趋势" in md

    def test_tech_ai_excludes_trends(self):
        """tech-ai 日报不应包含今日趋势分节(仅 comprehensive 有)"""
        results = [{
            "source": "arxiv_cs_ai",
            "status": "ok",
            "items": [{"title": "test test test", "url": "", "abstract": ""}],
        }]
        md = format_markdown(results, "tech-ai")
        assert "📈 今日趋势" not in md

    def test_academic_excludes_trends(self):
        """academic 日报不应包含今日趋势分节"""
        results = [{
            "source": "pubmed",
            "status": "ok",
            "items": [{"title": "test test test", "url": "", "abstract": ""}],
        }]
        md = format_markdown(results, "academic")
        assert "📈 今日趋势" not in md

    def test_new_sources_render_with_meta(self):
        """新源 kr_ai/techcrunch_ai 应使用 _SOURCE_META 渲染中文名"""
        results = [
            {"source": "kr_ai", "status": "ok",
             "items": [{"title": "AI测试", "url": "", "abstract": ""}]},
            {"source": "techcrunch_ai", "status": "ok",
             "items": [{"title": "AI test", "url": "", "abstract": ""}]},
        ]
        md = format_markdown(results, "tech-ai")
        assert "36氪 AI 快讯" in md
        assert "TechCrunch AI" in md

    def test_footer_after_trends(self):
        """趋势分节应在 footer(---) 之前"""
        md = format_markdown(SAMPLE_RESULTS, "comprehensive")
        trends_pos = md.find("📈 今日趋势")
        footer_pos = md.find("\n---\n")
        assert trends_pos < footer_pos
        assert trends_pos > 0

    def test_fail_source_shown_in_output(self):
        """失败的源应显示错误信息而非省略"""
        md = format_markdown(SAMPLE_RESULTS, "comprehensive")
        assert "暂不可用" in md
        assert "timeout" in md
