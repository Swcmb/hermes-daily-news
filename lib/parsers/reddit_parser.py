# reddit_parser.py — Reddit JSON 解析器
# 数据源:https://www.reddit.com/r/MachineLearning/top.json?t=day&limit=10
# 设计意图:解析 Reddit API 返回的 JSON,提取标题/URL/评分

import json
from . import sanitize, sanitize_url


def parse(raw_content: str, limit: int = 6, fetcher=None) -> list[dict]:
    """解析 Reddit JSON,返回统一 dict 列表。

    每条目结构:
        {"title": str, "url": str, "abstract": str,
         "meta": {"score": int, "permalink": str}}
    """
    if not raw_content:
        return []
    try:
        data = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return []
    # Reddit JSON 结构:data.children[i].data
    children = data.get("data", {}).get("children", [])
    if not children:
        return []
    items = []
    for child in children[:limit]:
        item = _parse_child(child)
        if item:
            items.append(item)
    return items


def _parse_child(child: dict) -> dict | None:
    """从单个 child 对象提取信息。"""
    data = child.get("data", {})
    if not data:
        return None
    title = data.get("title", "")
    if not title:
        return None
    title = sanitize(title, "title")
    # permalink 是相对路径,需拼接 reddit 域名
    permalink = data.get("permalink", "")
    url = data.get("url", "")
    # 优先用 permalink(讨论页),而非外部链接
    if permalink:
        full_url = sanitize_url(f"https://www.reddit.com{permalink}")
    else:
        full_url = sanitize_url(url)
    score = data.get("score", 0) or 0
    num_comments = data.get("num_comments", 0) or 0
    abstract = f"Reddit 评分:{score} | 评论:{num_comments}"
    return {
        "title": title,
        "url": full_url,
        "abstract": abstract,
        "meta": {"score": score, "num_comments": num_comments,
                 "permalink": permalink},
    }
