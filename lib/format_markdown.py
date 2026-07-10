#!/usr/bin/env python3
# format_markdown.py — JSON → 中文 Markdown 格式化
# 设计意图:将 fetch_worker 输出的统一 JSON 转换为推送用的 Markdown 日报
# 输入:stdin(JSON 数组) + 命令行参数(日报类型)
# 输出:stdout(Markdown 文本)

import json
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
    # academic 源
    "arxiv_stat_ml": ("🕸️", "图神经网络与ML",  "arXiv stat.ML 今日新论文"),
    "arxiv_qbio_gn": ("🧬", "基因组学",        "arXiv q-bio.GN 今日新论文"),
    "arxiv_qbio_qm": ("💊", "定量生物学",      "arXiv q-bio.QM 今日新论文"),
    "pubmed":        ("📚", "PubMed",         "ML/DL 最新文献"),
    "biorxiv":       ("🧪", "bioRxiv",        "近 7 天预印本"),
}

# 日报类型 → (总标题 emoji, 总标题名)
_TYPE_META = {
    "comprehensive": ("📰", "综合新闻"),
    "tech-ai":       ("📡", "AI科技"),
    "academic":      ("🧬", "学术前沿"),
}


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
