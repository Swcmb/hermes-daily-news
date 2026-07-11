# cache.py — 跨脚本文件缓存
# 设计意图:避免同一天内重复抓取,tech-ai(12:00)与 academic(18:00)共享 arXiv 缓存
# 缓存 key: sha1(source_name:url).json,加入 source_name 以隔离同 URL 不同 parser 的缓存
# (如 36kr 被 comprehensive 的 rss parser 和 tech-ai 的 news_filter parser 共用)

import hashlib
import json
import os
import time


# 默认缓存目录(可被 config 覆盖)
_DEFAULT_CACHE_DIR = "/tmp/hermes-news-cache"

# .done 标记文件目录与通配符
_DONE_MARKER_PATTERN = "/tmp/news-*.done"


def _cache_dir() -> str:
    """获取缓存目录(优先用环境变量,降级用默认值)。"""
    return os.environ.get("CACHE_DIR", _DEFAULT_CACHE_DIR)


def _cache_key(url: str, source_name: str = "") -> str:
    """根据 URL + 源名生成缓存文件名(sha1 防碰撞)。

    设计意图:同 URL 不同 parser(如 36kr 的 rss 与 news_filter)需要独立缓存,
    避免缓存污染。source_name 为空时退化为仅按 URL 哈希(向后兼容)。
    """
    raw = f"{source_name}:{url}" if source_name else url
    return hashlib.sha1(raw.encode("utf-8")).hexdigest() + ".json"


def _cache_path(url: str, source_name: str = "") -> str:
    """获取 URL 对应的缓存文件完整路径。"""
    return os.path.join(_cache_dir(), _cache_key(url, source_name))


def get_cache(url: str, ttl: int, source_name: str = "") -> dict | None:
    """读取缓存。命中且未过期返回 dict,否则返回 None。

    参数:
        url: 已替换占位符的最终 URL
        ttl: 缓存有效期(秒)
        source_name: 源名(用于隔离同 URL 不同 parser 的缓存,可选)
    """
    path = _cache_path(url, source_name)
    if not os.path.exists(path):
        return None
    # 检查文件修改时间是否在 TTL 内
    mtime = os.path.getmtime(path)
    if time.time() - mtime > ttl:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def set_cache(url: str, data: dict, source_name: str = "") -> None:
    """写入缓存(原子写入:先写 .tmp 再 rename)。

    参数:
        url: 已替换占位符的最终 URL
        data: 缓存数据
        source_name: 源名(用于隔离同 URL 不同 parser 的缓存,可选)
    """
    cache_dir = _cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(url, source_name)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.rename(tmp_path, path)  # 原子替换
    except OSError:
        # 写入失败时清理临时文件,降级为无缓存模式
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def clear_expired(cache_dir: str, retention_hours: int = 48) -> int:
    """清理缓存目录内超过保留时长的缓存文件,返回清理数量。"""
    if not os.path.isdir(cache_dir):
        return 0
    threshold = time.time() - retention_hours * 3600
    count = 0
    for name in os.listdir(cache_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(cache_dir, name)
        try:
            if os.path.getmtime(path) < threshold:
                os.unlink(path)
                count += 1
        except OSError:
            continue
    return count


def clear_done_markers(retention_hours: int = 48) -> int:
    """清理 /tmp/news-*.done 标记文件(供 fallback 机制用),返回清理数量。

    设计意图:独立于 clear_expired,避免历史标记干扰次日 fallback 判断。
    """
    import glob
    threshold = time.time() - retention_hours * 3600
    count = 0
    for path in glob.glob(_DONE_MARKER_PATTERN):
        try:
            if os.path.getmtime(path) < threshold:
                os.unlink(path)
                count += 1
        except OSError:
            continue
    return count
