"""36kr AI 关键词过滤 parser - 复用 rss_parser,按 AI 关键词过滤标题/摘要

设计意图:tech-ai 日报的"行业动态"维度复用 36kr RSS,但仅保留 AI 相关条目,
避免引入新 URL 造成性能消耗。keywords 由 fetch_worker 从 config.sh 的
AI_KEYWORDS 读取并传入,未配置时使用 DEFAULT_AI_KEYWORDS。
"""
from .rss_parser import parse as rss_parse

# AI 关键词默认列表(可由 config.sh 的 AI_KEYWORDS 配置覆盖)
DEFAULT_AI_KEYWORDS = [
    "AI", "LLM", "大模型", "GPT", "Agent", "融资",
    "OpenAI", "Google", "Anthropic", "人工智能",
    "机器学习", "深度学习", "芯片", "算力", "AGI",
]


def parse(raw_content: str, limit: int = 6, keywords: list[str] | None = None) -> list[dict]:
    """解析 RSS 并按 AI 关键词过滤标题/摘要

    Args:
        raw_content: RSS/Atom XML 原始内容
        limit: 过滤后保留的最大条目数
        keywords: AI 关键词列表,None 时使用 DEFAULT_AI_KEYWORDS

    Returns:
        过滤后的条目列表,结构与 rss_parser.parse 输出一致
    """
    if not raw_content or len(raw_content) < 100:
        return []
    if keywords is None:
        keywords = DEFAULT_AI_KEYWORDS
    # 多取 3 倍条目以便过滤后仍有足够数量
    items = rss_parse(raw_content, limit * 3)
    if not items:
        return []
    kw_lower = [kw.lower() for kw in keywords]
    filtered = []
    for item in items:
        title = item.get("title", "").lower()
        abstract = item.get("abstract", "").lower()
        # 标题或摘要命中任一关键词即保留
        if any(kw in title or kw in abstract for kw in kw_lower):
            filtered.append(item)
        if len(filtered) >= limit:
            break
    return filtered[:limit]
