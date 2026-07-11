#!/usr/bin/env python3
# fetch_worker.py — 智讯日报并行抓取入口
# 设计意图:接收 --type 参数,并行抓取所有源,输出统一 JSON 到 stdout
# 关键设计:load_config() 内部自行 source config.sh,不依赖外部 shell 预先 source

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# 确保能导入同包模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import cache, dedup
from lib.parsers import rss_parser, arxiv_parser, github_parser
from lib.parsers import hn_parser, producthunt_parser, reddit_parser, pubmed_parser
from lib.parsers import news_filter


# ===== 源注册表(源名 → URL环境变量名, parser类型, TTL环境变量名, limit环境变量名) =====
SOURCE_REGISTRY = {
    # comprehensive 源(中文)
    "zhihu":         ("ZHIHU_URL",         "rss",       "CACHE_TTL_RSS",    "ZHIHU_LIMIT"),
    "36kr":          ("KR_URL",            "rss",       "CACHE_TTL_RSS",    "KR_LIMIT"),
    "nowcoder":      ("NOWCODER_URL",      "rss",       "CACHE_TTL_RSS",    "NOWCODER_LIMIT"),
    "weibo":         ("WEIBO_URL",         "rss",       "CACHE_TTL_RSS",    "WEIBO_LIMIT"),
    "baidu":         ("BAIDU_URL",         "rss",       "CACHE_TTL_RSS",    "BAIDU_LIMIT"),
    # tech-ai 源(英文 + 中文行业动态)
    "arxiv_cs_ai":   ("ARXIV_AI_URL",      "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "arxiv_cs_lg":   ("ARXIV_LG_URL",      "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "github_ai":     ("GITHUB_AI_URL",     "github",    "CACHE_TTL_GITHUB", "GITHUB_LIMIT"),
    "hn":            ("HN_URL",            "hn",        "CACHE_TTL_API",    "HN_LIMIT"),
    "producthunt":   ("PRODUCTHUNT_URL",   "producthunt","CACHE_TTL_API",   "PRODUCTHUNT_LIMIT"),
    "reddit_ml":     ("REDDIT_ML_URL",     "reddit",    "CACHE_TTL_API",    "REDDIT_LIMIT"),
    "kr_ai":         ("KR_AI_URL",         "news_filter","CACHE_TTL_RSS",   "KR_AI_LIMIT"),
    "techcrunch_ai": ("TECHCRUNCH_AI_URL", "rss",       "CACHE_TTL_RSS",    "TECHCRUNCH_AI_LIMIT"),
    # academic 源(英文)
    "arxiv_stat_ml": ("ARXIV_STATML_URL",  "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "arxiv_qbio_gn": ("ARXIV_QBIO_GN_URL", "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "arxiv_qbio_qm": ("ARXIV_QBIO_QM_URL", "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "pubmed":        ("PUBMED_URL",        "pubmed",    "CACHE_TTL_API",    "PUBMED_LIMIT"),
    "biorxiv":       ("BIORXIV_URL",       "pubmed",    "CACHE_TTL_API",    "BIORXIV_LIMIT"),
}

# parser 类型 → 解析函数的分发表
_PARSER_DISPATCH = {
    "rss": rss_parser.parse,
    "arxiv": arxiv_parser.parse,
    "github": github_parser.parse,
    "hn": hn_parser.parse,
    "producthunt": producthunt_parser.parse,
    "reddit": reddit_parser.parse,
    "pubmed": pubmed_parser.parse,
    "news_filter": news_filter.parse,
}

# 日报类型 → config 中的源列表变量名
_TYPE_SOURCES = {
    "comprehensive": "COMPREHENSIVE_SOURCES",
    "tech-ai": "TECH_AI_SOURCES",
    "academic": "ACADEMIC_SOURCES",
}


def load_config() -> dict:
    """基于 __file__ 定位项目根,内部 source config.sh 并解析环境变量。

    设计意图:无论 agent 模式(LLM 直接执行 python3)还是 no-agent 模式(Shell 调用),
    fetch_worker 都能自行加载配置,不依赖外部 shell 预先 source config.sh。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_sh = os.path.join(project_root, "config", "config.sh")
    if not os.path.exists(config_sh):
        return {}
    # 通过 subprocess 调用 bash source 并导出所有变量
    # set -a:自动导出后续设置的变量,使 env 能读取
    result = subprocess.run(
        ["bash", "-c", f'set -a && source "{config_sh}" && env -0'],
        capture_output=True, text=True
    )
    config = {}
    for entry in result.stdout.split("\0"):
        if "=" in entry:
            key, _, val = entry.partition("=")
            config[key] = val
    return config


def replace_placeholders(url: str) -> str:
    """替换 URL 中的动态占位符({7d_ago}/{start_date}/{end_date})。"""
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    placeholders = {
        "7d_ago": week_ago.strftime("%Y-%m-%d"),
        "start_date": week_ago.strftime("%Y-%m-%d"),
        "end_date": today.strftime("%Y-%m-%d"),
    }

    def replacer(match):
        key = match.group(1)
        if key in placeholders:
            return placeholders[key]
        # 未识别的占位符保持原样
        return match.group(0)

    return re.sub(r"\{(\w+)\}", replacer, url)


def resolve_sources(args, config: dict) -> list[str]:
    """解析要抓取的源列表(--sources 优先,否则按 --type 从 config 读取)。"""
    if args.sources:
        return [s.strip() for s in args.sources.split(",") if s.strip()]
    sources_var = _TYPE_SOURCES.get(args.type, "")
    sources_str = config.get(sources_var, "")
    return [s.strip() for s in sources_str.split(",") if s.strip()]


def _http_fetch(url: str, config: dict, timeout: int) -> str:
    """执行 HTTP 请求,返回响应文本。失败抛异常。"""
    user_agent = config.get("USER_AGENT", "hermes-daily-news/2.0")
    github_token = config.get("GITHUB_TOKEN", "")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", user_agent)
    # GitHub API 认证(可选)
    if "api.github.com" in url and github_token:
        req.add_header("Authorization", f"token {github_token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_single(source: str, config: dict, no_cache: bool = False) -> dict:
    """抓取单个源,返回统一结构 dict。

    流程:缓存检查 → HTTP(重试)→ 解析 → 返回
    每源独立 try/except,失败不阻断其他源。
    """
    start_ms = time.time()
    registry = SOURCE_REGISTRY.get(source)
    if not registry:
        return _fail_result(source, f"未知源名: {source}", start_ms)

    url_var, parser_type, ttl_var, limit_var = registry
    raw_url = config.get(url_var, "")
    if not raw_url:
        return _fail_result(source, f"URL 未配置({url_var})", start_ms)

    url = replace_placeholders(raw_url)
    ttl = int(config.get(ttl_var, "1800"))
    limit = int(config.get(limit_var, "10"))

    # 缓存命中检查(传入 source_name 以隔离同 URL 不同 parser 的缓存)
    if not no_cache:
        cached = cache.get_cache(url, ttl, source_name=source)
        if cached is not None:
            return _ok_result(source, parser_type, cached["items"], start_ms, cache_hit=True)

    # HTTP 抓取 + 重试
    timeout = int(config.get("TIMEOUT_HTTP", "12"))
    retry_max = int(config.get("RETRY_MAX", "2"))
    backoff_base = int(config.get("RETRY_BACKOFF_BASE", "1"))
    raw_content = None
    last_error = ""
    for attempt in range(retry_max + 1):
        try:
            raw_content = _http_fetch(url, config, timeout)
            break
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            # 4xx 不重试
            if 400 <= e.code < 500:
                break
        except Exception as e:
            # 异常消息可能为空,降级用异常类型名
            last_error = str(e)[:100] or type(e).__name__
        # 指数退避
        if attempt < retry_max:
            time.sleep(backoff_base * (2 ** attempt))

    if not raw_content:
        return _fail_result(source, f"{last_error} after {retry_max} retries", start_ms)

    # 解析
    parse_func = _PARSER_DISPATCH.get(parser_type)
    if parse_func is None:
        return _fail_result(source, f"parser 类型 '{parser_type}' 尚未实现", start_ms)
    try:
        # PubMed 需两步请求(esearch→esummary),传入 fetcher 回调供第二步使用
        if parser_type == "pubmed":
            fetcher = lambda url: _http_fetch(url, config, timeout)
            items = parse_func(raw_content, limit, fetcher=fetcher)
        elif parser_type == "news_filter":
            # news_filter 需从 config 读取 AI_KEYWORDS 并传入,用于过滤 AI 相关条目
            keywords_str = config.get("AI_KEYWORDS", "")
            keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
            items = parse_func(raw_content, limit, keywords=keywords)
        else:
            items = parse_func(raw_content, limit)
    except Exception as e:
        return _fail_result(source, f"解析失败: {e}", start_ms)

    # 写入缓存(传入 source_name 以隔离同 URL 不同 parser 的缓存)
    if not no_cache and items:
        cache.set_cache(url, {"items": items, "fetched_at": _now_iso()}, source_name=source)

    return _ok_result(source, parser_type, items, start_ms)


def fetch_all(sources: list[str], config: dict, no_cache: bool = False) -> list[dict]:
    """并行抓取所有源(ThreadPoolExecutor)。"""
    max_workers = int(config.get("MAX_WORKERS", "4"))
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(fetch_single, src, config, no_cache): src
            for src in sources
        }
        for future in as_completed(future_map):
            results.append(future.result())
    return results


def health_check(config: dict) -> int:
    """健康检查模式:测各源可达性,输出状态表。"""
    all_sources = list(SOURCE_REGISTRY.keys())
    print(f"{'源名':<20} {'HTTP状态':<10} {'耗时':<10} {'可达'}")
    print("-" * 55)
    ok_count = 0
    for source in all_sources:
        registry = SOURCE_REGISTRY[source]
        url_var = registry[0]
        raw_url = config.get(url_var, "")
        if not raw_url:
            print(f"{source:<20} {'N/A':<10} {'-':<10} {'未配置'}")
            continue
        url = replace_placeholders(raw_url)
        start = time.time()
        try:
            timeout = int(config.get("TIMEOUT_HTTP", "12"))
            _http_fetch(url, config, timeout)
            elapsed = f"{int((time.time() - start) * 1000)}ms"
            print(f"{source:<20} {'200':<10} {elapsed:<10} {'✓'}")
            ok_count += 1
        except urllib.error.HTTPError as e:
            elapsed = f"{int((time.time() - start) * 1000)}ms"
            print(f"{source:<20} {str(e.code):<10} {elapsed:<10} {'✗'}")
        except Exception as e:
            elapsed = f"{int((time.time() - start) * 1000)}ms"
            print(f"{source:<20} {'ERR':<10} {elapsed:<10} {'✗'}")
    print(f"\n可达: {ok_count}/{len(all_sources)}")
    return 0 if ok_count == len(all_sources) else 1


def main():
    parser = argparse.ArgumentParser(description="智讯日报并行抓取入口")
    parser.add_argument("--type", choices=list(_TYPE_SOURCES.keys()),
                        help="日报类型")
    parser.add_argument("--sources", help="覆盖源列表(逗号分隔)")
    parser.add_argument("--no-cache", action="store_true", help="跳过缓存")
    parser.add_argument("--health", action="store_true", help="健康检查模式")
    args = parser.parse_args()

    config = load_config()
    if not config:
        print("错误:配置加载失败", file=sys.stderr)
        return 2

    # 启动时清理过期缓存与 .done 标记
    cache_dir = config.get("CACHE_DIR", "/tmp/hermes-news-cache")
    retention = int(config.get("CACHE_RETENTION_HOURS", "48"))
    cache.clear_expired(cache_dir, retention)
    cache.clear_done_markers(retention)

    # 健康检查模式
    if args.health:
        return health_check(config)

    # 解析源列表
    if not args.type and not args.sources:
        print("错误:必须指定 --type 或 --sources", file=sys.stderr)
        return 2
    sources = resolve_sources(args, config)
    if not sources:
        print("错误:未解析到任何数据源", file=sys.stderr)
        return 2

    # 并行抓取
    results = fetch_all(sources, config, args.no_cache)

    # 去重
    results = dedup.dedup(results)

    # 输出 JSON
    print(json.dumps(results, ensure_ascii=False))

    # 退出码:全成功 0,部分失败 1,全失败 2
    ok_count = sum(1 for r in results if r["status"] in ("ok", "cache_hit"))
    if ok_count == len(results):
        return 0
    elif ok_count == 0:
        return 2
    return 1


# ===== 辅助函数 =====

def _now_iso() -> str:
    """当前时间 ISO8601 格式。"""
    from datetime import timezone
    tz = timezone(timedelta(hours=8))  # Asia/Shanghai
    return datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S%z")


def _ok_result(source: str, source_type: str, items: list,
               start_ms: float, cache_hit: bool = False) -> dict:
    """构造成功结果。"""
    return {
        "source": source,
        "source_type": source_type,
        "fetched_at": _now_iso(),
        "status": "cache_hit" if cache_hit else "ok",
        "item_count": len(items),
        "cache_hit": cache_hit,
        "elapsed_ms": int((time.time() - start_ms) * 1000),
        "items": items,
    }


def _fail_result(source: str, error: str, start_ms: float) -> dict:
    """构造失败结果。"""
    return {
        "source": source,
        "fetched_at": _now_iso(),
        "status": "fail",
        "error": error,
        "item_count": 0,
        "elapsed_ms": int((time.time() - start_ms) * 1000),
        "items": [],
    }


if __name__ == "__main__":
    sys.exit(main())
