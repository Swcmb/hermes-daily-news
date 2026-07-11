#!/usr/bin/env python3
# format_markdown.py — JSON → 中文 Markdown 格式化
# 设计意图:将 fetch_worker 输出的统一 JSON 转换为推送用的 Markdown 日报
# 输入:stdin(JSON 数组) + 命令行参数(日报类型)
# 输出:stdout(Markdown 文本)

import json
import re
import sys
from datetime import datetime, timedelta, timezone

# 源名 → (emoji, 中文分节名, 副标题模板)
_SOURCE_META = {
    # comprehensive 源
    "zhihu":       ("🇨🇳", "国内热点",       "知乎热榜 Top {n}"),
    "36kr":        ("💹", "财经科技快讯",    "36氪 Top {n}"),
    "nowcoder":    ("💻", "行业热议",        "牛客 Top {n}"),
    "weibo":       ("🔥", "微博热搜",        "微博 Top {n}"),
    "baidu":       ("🔍", "百度热搜",        "百度 Top {n}"),
    # tech-ai 源
    "arxiv_cs_ai": ("🤖", "AI 学术前沿",     "arXiv cs.AI 今日新论文"),
    "arxiv_cs_lg": ("🧠", "机器学习新成果",  "arXiv cs.LG 今日新论文"),
    "github_ai":   ("⭐", "GitHub Trending", "近 7 天热门 AI 仓库"),
    "hn":          ("🔧", "Hacker News",     "HN 首页 Top {n}"),
    "producthunt": ("🚀", "Product Hunt",    "今日新产品 Top {n}"),
    "reddit_ml":   ("💬", "Reddit r/ML",     "机器学习社区热议 Top {n}"),
    "kr_ai":         ("📰", "36氪 AI 快讯",   "36氪 AI 相关 Top {n}"),
    "techcrunch_ai": ("🌐", "TechCrunch AI", "TechCrunch AI Top {n}"),
    # academic 源
    "arxiv_stat_ml": ("🕸️", "图神经网络与ML",  "arXiv stat.ML 今日新论文"),
    "arxiv_qbio_gn": ("🧬", "基因组学",        "arXiv q-bio.GN 今日新论文"),
    "arxiv_qbio_qm": ("💊", "定量生物学",      "arXiv q-bio.QM 今日新论文"),
    "pubmed":        ("📚", "PubMed",         "ML/DL 最新文献"),
    "biorxiv":       ("🧪", "bioRxiv",        "近 7 天预印本"),
}

# 中文停用词(高频无意义词,过滤掉避免误判为趋势)
_CN_STOPWORDS = {"的", "了", "在", "是", "今日", "发布", "推出", "宣布",
                 "一个", "可以", "已经", "将", "与", "和", "中", "上", "新"}
# 英文停用词
_EN_STOPWORDS = {"the", "a", "an", "to", "of", "in", "on", "for",
                 "and", "or", "is", "are", "was", "with", "by"}

# 日报类型 → (总标题 emoji, 总标题名)
_TYPE_META = {
    "comprehensive": ("📰", "综合新闻"),
    "tech-ai":       ("📡", "AI科技"),
    "academic":      ("🧬", "学术前沿"),
}


def _count_words(titles: list[str]) -> dict[str, int]:
    """对标题列表做词频统计(中文 2-3 字滑窗,英文空格分词)。

    设计意图:零 LLM 消耗的趋势分析,同标题内去重避免重复计数。
    """
    freq = {}
    for title in titles:
        # 同标题内去重:同一词在同一标题中出现多次只计一次
        seen_in_title = set()
        # 中文 2-3 字滑窗(4 字滑窗噪音过多,不采用)
        for n in (2, 3):
            for i in range(len(title) - n + 1):
                word = title[i:i+n]
                if word not in _CN_STOPWORDS and word not in seen_in_title:
                    seen_in_title.add(word)
                    freq[word] = freq.get(word, 0) + 1
        # 英文空格分词(最小长度 3)
        for word in re.findall(r'[a-zA-Z]{3,}', title):
            word_lower = word.lower()
            if word_lower not in _EN_STOPWORDS and word_lower not in seen_in_title:
                seen_in_title.add(word_lower)
                freq[word_lower] = freq.get(word_lower, 0) + 1
    return freq


def _generate_trends(results: list[dict]) -> str:
    """基于各源条目标题词频,生成 3 条趋势(零 LLM 消耗)。

    设计意图:为 comprehensive 日报提供基于数据归纳的趋势点评,
    对应参考提示词中"今日趋势点评"模式。最小词频阈值 count >= 2。
    """
    titles = []
    for source in results:
        if source.get("status") in ("ok", "cache_hit"):
            for item in source.get("items", []):
                titles.append(item.get("title", ""))
    word_freq = _count_words(titles)
    # 最小词频阈值:count >= 2 才纳入候选(单次出现的词不作为趋势)
    candidates = [(w, c) for w, c in word_freq.items() if c >= 2]
    # 按词频降序,取 top 3
    top3 = sorted(candidates, key=lambda x: -x[1])[:3]
    if not top3:
        return ""
    lines = ["## 📈 今日趋势", ""]
    for i, (word, count) in enumerate(top3, 1):
        lines.append(f"{i}. **{word}** — 今日 {count} 个源提及")
    lines.append("")
    return "\n".join(lines)


def format_markdown(results: list[dict], news_type: str) -> str:
    """将 fetch_worker 的 JSON 结果格式化为 Markdown 日报。"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    date_str = now.strftime("%Y年%-m月%-d日")
    ts = now.strftime("%Y-%m-%dT%H:%M:%S%z")

    type_emoji, type_name = _TYPE_META.get(news_type, ("📋", "日报"))
    lines = [f"{type_emoji} 智讯·{type_name}日报 — {date_str}", f"🕐 {ts}", ""]

    for result in results:
        source = result.get("source", "")
        status = result.get("status", "fail")
        items = result.get("items", [])
        meta = _SOURCE_META.get(source, ("📄", source, ""))
        emoji, name, subtitle = meta

        # 副标题填充条数
        if subtitle:
            subtitle = subtitle.format(n=len(items))

        lines.append(f"## {emoji} {name}")
        if subtitle:
            lines.append(f"（{subtitle}）")
        lines.append("")

        if status == "fail":
            error = result.get("error", "未知错误")
            lines.append(f"（暂不可用：{error}）")
            lines.append("")
            continue
        if not items:
            lines.append("（今日暂无新条目）")
            lines.append("")
            continue

        # 格式化条目
        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            abstract = item.get("abstract", "")
            item_meta = item.get("meta", {})

            lines.append(f"{i}. **{title}**")
            if url:
                lines.append(f"   链接：{url}")
            if abstract:
                lines.append(f"   _{abstract}_")
            # arXiv 论文显示 arxiv_id
            arxiv_id = item_meta.get("arxiv_id", "")
            if arxiv_id:
                lines.append(f"   arXiv:{arxiv_id}")
            # GitHub 仓库显示星标和语言
            stars = item_meta.get("stars")
            if stars is not None:
                lang = item_meta.get("language", "")
                lines.append(f"   ⭐{stars}" + (f" ({lang})" if lang else ""))
            lines.append("")

    # comprehensive 日报在 footer 前插入今日趋势分节(零 LLM 消耗)
    if news_type == "comprehensive":
        trends = _generate_trends(results)
        if trends:
            lines.append(trends)

    # 结尾
    lines.append("---")
    lines.append(f"⏱ 数据采集时间：{ts}")
    lines.append(f"📡 数据源：{', '.join(r['source'] for r in results)}")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="JSON → Markdown 格式化")
    parser.add_argument("type", choices=list(_TYPE_META.keys()),
                        help="日报类型")
    args = parser.parse_args()
    try:
        results = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        print("错误:无法解析 JSON 输入", file=sys.stderr)
        sys.exit(1)
    print(format_markdown(results, args.type))


if __name__ == "__main__":
    main()
