# dedup.py — 单次运行内跨源去重
# 设计意图:避免同一条目在不同源重复出现,O(n) 极低消耗
# 策略:URL 精确匹配 + 标题 hash(不使用 NLP 相似度,消耗大)

import hashlib
import re
from urllib.parse import urlparse, parse_qs, urlencode

from .parsers import SOURCE_PRIORITY


def dedup(results: list[dict]) -> list[dict]:
    """跨源去重,保留首次出现(按源优先级)的条目。

    输入输出契约:
        输入:fetch_worker 的源级别结果数组(每个元素含 source/items 字段)
        输出:同结构数组,去重后的 items 从后续源中移除,item_count 同步更新
    """
    seen_urls: set[str] = set()
    seen_title_hashes: set[str] = set()
    # 按源优先级排序(索引越小越靠前),稳定排序保留同优先级源的原始顺序
    priority_map = {s: i for i, s in enumerate(SOURCE_PRIORITY)}
    sorted_results = sorted(
        results,
        key=lambda r: priority_map.get(r.get("source", ""), len(SOURCE_PRIORITY))
    )
    for result in sorted_results:
        if result.get("status") != "ok":
            continue
        kept = []
        for item in result.get("items", []):
            url = _normalize_url(item.get("url", ""))
            title_hash = _title_hash(item.get("title", ""))
            # URL 或标题 hash 命中则跳过
            if url and url in seen_urls:
                continue
            if title_hash and title_hash in seen_title_hashes:
                continue
            if url:
                seen_urls.add(url)
            if title_hash:
                seen_title_hashes.add(title_hash)
            kept.append(item)
        result["items"] = kept
        result["item_count"] = len(kept)
    return sorted_results


def _normalize_url(url: str) -> str:
    """归一化 URL:去除跟踪参数(utm_*/fbclid/gclid/ref/source)。"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ""
        # 过滤 query 中的跟踪参数
        qs = parse_qs(parsed.query)
        tracking_prefixes = ("utm_", "fbclid", "gclid", "ref", "source")
        filtered = {
            k: v for k, v in qs.items()
            if not any(k.lower().startswith(p) for p in tracking_prefixes)
        }
        new_query = urlencode(filtered, doseq=True)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" + (
            f"?{new_query}" if new_query else ""
        )
    except Exception:
        return url


def _title_hash(title: str) -> str:
    """标题归一化后 hash:lowercase → 去标点 → 分词排序 → sha1 前 16 字节。"""
    if not title:
        return ""
    lower = title.lower()
    # 保留中英文字符与数字,去标点
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]', ' ', lower)
    words = sorted(cleaned.split())
    normalized = ''.join(words)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
