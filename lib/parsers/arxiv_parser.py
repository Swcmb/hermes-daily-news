# arxiv_parser.py — arXiv RSS 专用解析器
# 适用源:arXiv cs.AI/cs.LG/stat.ML/q-bio.GN/q-bio.QM
# 设计意图:CDATA 解包 + abstract 清洗(去 arXiv 前缀)+ arxiv_id 提取

import re
from . import sanitize, sanitize_url


def parse(raw_content: str, limit: int = 6) -> list[dict]:
    """解析 arXiv RSS XML,返回统一 dict 列表。

    每条目结构:
        {"title": str, "url": str, "abstract": str,
         "meta": {"arxiv_id": str, "lang": "en"}}
    """
    if not raw_content or len(raw_content) < 500:
        return []
    items = []
    for block in re.findall(r'<item>(.*?)</item>', raw_content, re.DOTALL):
        if len(items) >= limit:
            break
        item = _parse_block(block)
        if item and item["title"]:
            items.append(item)
    return items


def _parse_block(block: str) -> dict | None:
    """从单个 <item> 块提取 arXiv 论文信息。"""
    m_title = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
    if not m_title:
        return None
    title = _strip_cdata(m_title.group(1))
    title = sanitize(title, "title")

    m_link = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
    link = sanitize_url(_strip_cdata(m_link.group(1))) if m_link else ""

    # 从 link 中提取 arxiv_id
    arxiv_id = ""
    if link:
        m_id = re.search(r'arxiv\.org/abs/([\w\./\-]+)', link)
        if m_id:
            arxiv_id = m_id.group(1)

    abstract = ""
    m_desc = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
    if m_desc:
        desc = _strip_cdata(m_desc.group(1))
        # 去除 arXiv RSS description 中的固定前缀
        desc = re.sub(
            r'arXiv:[\w\./\-]+\s*\w*\s*Announce Type:\s*\w+\s*Abstract:\s*',
            '', desc
        )
        abstract = sanitize(desc, "abstract")

    return {
        "title": title,
        "url": link,
        "abstract": abstract,
        "meta": {"arxiv_id": arxiv_id, "lang": "en"},
    }


def _strip_cdata(text: str) -> str:
    """解包 CDATA 段并压缩空白。"""
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    return re.sub(r'\s+', ' ', text).strip()
