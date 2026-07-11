# pubmed_parser.py — PubMed E-utilities + bioRxiv API 解析器
# 数据源:
#   PubMed: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi (两步:esearch→esummary)
#   bioRxiv: https://api.biorxiv.org/details/biorxiv/{start_date}/{end_date}/0/25
# 设计意图:PubMed 需两步请求(esearch 取 ID → esummary 取详情),通过 fetcher 回调实现

import json
import re
import urllib.request
from . import sanitize, sanitize_url


def parse(raw_content: str, limit: int = 6, fetcher=None) -> list[dict]:
    """解析 PubMed XML 或 bioRxiv JSON,返回统一 dict 列表。

    参数:
        raw_content: 第一步响应(esearch XML 或 bioRxiv JSON)
        limit: 最大条目数
        fetcher: 可选的 HTTP 请求回调(用于 PubMed 第二步 esummary)
    """
    if not raw_content:
        return []
    # 判断是 bioRxiv JSON 还是 PubMed XML
    if raw_content.strip().startswith("{"):
        return _parse_biorxiv(raw_content, limit)
    return _parse_pubmed(raw_content, limit, fetcher)


def _parse_pubmed(esearch_xml: str, limit: int, fetcher=None) -> list[dict]:
    """解析 PubMed:esearch XML → 提取 PMID → esummary 获取详情。"""
    # 从 esearch XML 中提取 PMID 列表
    pmids = re.findall(r'<Id>(\d+)</Id>', esearch_xml)
    if not pmids:
        return []
    pmids = pmids[:limit]
    # 构造 esummary URL
    id_list = ",".join(pmids)
    esummary_url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=pubmed&id={id_list}"
    )
    # 获取 esummary 响应(用 fetcher 回调或直接 urllib)
    try:
        if fetcher:
            esummary_xml = fetcher(esummary_url)
        else:
            req = urllib.request.Request(esummary_url)
            req.add_header("User-Agent", "hermes-daily-news/2.0")
            with urllib.request.urlopen(req, timeout=12) as resp:
                esummary_xml = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    return _parse_esummary(esummary_xml, pmids)


def _parse_esummary(xml: str, pmids: list[str]) -> list[dict]:
    """解析 esummary XML,提取标题/摘要/作者。"""
    items = []
    for pmid in pmids:
        # 每个 DocSum 块含 Id + Item 标签
        pattern = rf'<DocSum>.*?<Id>{pmid}</Id>(.*?)</DocSum>'
        m = re.search(pattern, xml, re.DOTALL)
        if not m:
            continue
        block = m.group(1)
        title = _extract_item(block, "Title")
        if not title:
            continue
        title = sanitize(title, "title")
        abstract = _extract_item(block, "Abstract") or ""
        abstract = sanitize(abstract, "abstract")
        authors = _extract_authors(block)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        items.append({
            "title": title,
            "url": url,
            "abstract": abstract,
            "meta": {"pmid": pmid, "authors": authors, "lang": "en"},
        })
    return items


def _extract_item(block: str, name: str) -> str:
    """从 DocSum 块中提取指定名称的 Item 值。"""
    pattern = rf'<Item Name="{name}"[^>]*>(.*?)</Item>'
    m = re.search(pattern, block, re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_authors(block: str) -> str:
    """从 DocSum 块中提取作者列表(前 3 位)。"""
    authors = re.findall(r'<Item Name="Author"[^>]*>(.*?)</Item>', block, re.DOTALL)
    authors = [a.strip() for a in authors[:3]]
    if len(authors) < 3:
        # 可能用 LastAuthor 字段
        pass
    return ", ".join(authors)


def _parse_biorxiv(json_str: str, limit: int) -> list[dict]:
    """解析 bioRxiv details API JSON。"""
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return []
    articles = data.get("collection", [])
    if not articles:
        return []
    items = []
    for art in articles[:limit]:
        item = _parse_biorxiv_article(art)
        if item:
            items.append(item)
    return items


def _parse_biorxiv_article(art: dict) -> dict | None:
    """从单个 bioRxiv 文章对象提取信息。"""
    title = art.get("title", "")
    if not title:
        return None
    title = sanitize(title, "title")
    abstract = art.get("abstract", "")
    abstract = sanitize(abstract, "abstract")
    doi = art.get("doi", "")
    url = sanitize_url(f"https://www.biorxiv.org/content/{doi}v1") if doi else ""
    authors = art.get("authors", "")
    category = art.get("category", "")
    return {
        "title": title,
        "url": url,
        "abstract": abstract,
        "meta": {"doi": doi, "authors": authors, "category": category,
                 "lang": "en"},
    }
