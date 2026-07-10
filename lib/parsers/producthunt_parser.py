# producthunt_parser.py — Product Hunt RSS 解析器
# 数据源:https://www.producthunt.com/feed
# 设计意图:复用 rss_parser 通用解析,补充 Product Hunt 特有字段

import re
from . import sanitize, sanitize_url
from .rss_parser import parse as _rss_parse, _parse_block, _strip_cdata


def parse(raw_content: str, limit: int = 6, fetcher=None) -> list[dict]:
    """解析 Product Hunt RSS,返回统一 dict 列表。

    每条目结构:
        {"title": str, "url": str, "abstract": str, "meta": {"votes": str}}
    """
    if not raw_content or len(raw_content) < 100:
        return []
    items = []
    for block in re.findall(r'<item>(.*?)</item>', raw_content, re.DOTALL):
        if len(items) >= limit:
            break
        item = _parse_block(block)
        if not item or not item["title"]:
            continue
        # Product Hunt 的 description 中可能含 votes 信息
        votes = _extract_votes(block)
        item["meta"] = {"votes": votes}
        items.append(item)
    return items


def _extract_votes(block: str) -> str:
    """从 Product Hunt RSS 块中提取 votes 信息(如有)。"""
    m_desc = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
    if not m_desc:
        return ""
    desc = _strip_cdata(m_desc.group(1))
    # Product Hunt 的 description 中可能含 "▲ 123" 格式的 votes
    m_votes = re.search(r'[▲▲]\s*(\d+)', desc)
    return m_votes.group(1) if m_votes else ""
