# rss_parser.py — RSS/Atom 通用解析器
# 适用源:知乎/36氪/牛客/微博/百度(均为中文 RSS)
# 设计意图:正则提取 <item> 块,容忍 XML 截断,不依赖完整 XML 解析器

import re
from . import sanitize, sanitize_url


def parse(raw_content: str, limit: int = 10) -> list[dict]:
    """解析 RSS/Atom XML,返回统一 dict 列表。

    每条目结构:
        {"title": str, "url": str, "abstract": str, "meta": {}}
    容忍截断:正则匹配,不要求完整 XML 文档。
    """
    if not raw_content or len(raw_content) < 100:
        return []
    items = []
    # 提取 <item>...</item> 块(DOTALL 允许跨行)
    for block in re.findall(r'<item>(.*?)</item>', raw_content, re.DOTALL):
        if len(items) >= limit:
            break
        item = _parse_block(block)
        if item and item["title"]:
            items.append(item)
    return items


def _parse_block(block: str) -> dict | None:
    """从单个 <item> 块提取 title/link/description。"""
    m_title = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
    if not m_title:
        return None
    # 解包 CDATA
    title = _strip_cdata(m_title.group(1))
    title = sanitize(title, "title")

    m_link = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
    link = sanitize_url(_strip_cdata(m_link.group(1))) if m_link else ""

    abstract = ""
    m_desc = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
    if m_desc:
        desc = _strip_cdata(m_desc.group(1))
        abstract = sanitize(desc, "abstract")

    return {"title": title, "url": link, "abstract": abstract, "meta": {}}


def _strip_cdata(text: str) -> str:
    """解包 CDATA 段并压缩空白。"""
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    return re.sub(r'\s+', ' ', text).strip()
