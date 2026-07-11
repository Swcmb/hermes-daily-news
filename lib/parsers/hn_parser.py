# hn_parser.py — Hacker News Algolia API 解析器
# 数据源:https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=10
# 设计意图:解析 Algolia 返回的 JSON,提取标题/URL/积分/评论数

import json
from . import sanitize, sanitize_url


def parse(raw_content: str, limit: int = 10, fetcher=None) -> list[dict]:
    """解析 HN Algolia API JSON,返回统一 dict 列表。

    每条目结构:
        {"title": str, "url": str, "abstract": str,
         "meta": {"points": int, "num_comments": int}}
    """
    if not raw_content:
        return []
    try:
        data = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return []
    hits = data.get("hits", [])
    if not hits:
        return []
    items = []
    for hit in hits[:limit]:
        item = _parse_hit(hit)
        if item:
            items.append(item)
    return items


def _parse_hit(hit: dict) -> dict | None:
    """从单个 hit 对象提取信息。"""
    title = hit.get("title") or hit.get("story_title") or ""
    if not title:
        return None
    title = sanitize(title, "title")
    # 优先用 url,其次 story_url
    url = hit.get("url") or hit.get("story_url") or ""
    url = sanitize_url(url)
    points = hit.get("points", 0) or 0
    num_comments = hit.get("num_comments", 0) or 0
    abstract = f"HN 积分:{points} | 评论:{num_comments}"
    return {
        "title": title,
        "url": url,
        "abstract": abstract,
        "meta": {"points": points, "num_comments": num_comments},
    }
