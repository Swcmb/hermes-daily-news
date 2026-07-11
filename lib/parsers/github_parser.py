# github_parser.py — GitHub Search API JSON 解析器
# 适用源:GitHub Trending(github_ai)
# 设计意图:解析 Search API 返回的 JSON,提取仓库元数据

import json
from . import sanitize


def parse(raw_content: str, limit: int = 8) -> list[dict]:
    """解析 GitHub Search API JSON,返回统一 dict 列表。

    每条目结构:
        {"title": str, "url": str, "abstract": str,
         "meta": {"stars": int, "language": str}}
    """
    if not raw_content:
        return []
    try:
        data = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return []
    items_data = data.get("items", [])
    if not items_data:
        return []
    items = []
    for repo in items_data[:limit]:
        item = _parse_repo(repo)
        if item:
            items.append(item)
    return items


def _parse_repo(repo: dict) -> dict | None:
    """从单个 repo JSON 对象提取信息。"""
    full_name = repo.get("full_name", "")
    if not full_name:
        return None
    title = sanitize(full_name, "title")
    url = repo.get("html_url", "")
    # description 可能含换行,清洗时压缩为单行
    desc = (repo.get("description") or "").replace("\n", " ")
    abstract = sanitize(desc, "abstract")
    stars = repo.get("stargazers_count", 0)
    language = repo.get("language") or ""
    return {
        "title": title,
        "url": url,
        "abstract": abstract,
        "meta": {"stars": stars, "language": language},
    }
