# parsers 包 — 智讯日报数据源解析器集合
# 设计意图:每个 parser 为纯函数模块,仅暴露 parse(raw_content, limit) -> list[dict]
# 内容安全:所有 parser 在解析后统一调用 sanitize 清洗

import html
import re


def sanitize(text: str, field_type: str = "generic") -> str:
    """清洗文本:剥离HTML标签、反转义HTML实体、压缩空白、截断超长字段。

    设计意图:统一的内容安全入口,防止 XSS 与 Markdown 格式破坏。

    参数:
        text: 待清洗文本
        field_type: 字段类型("title"/"abstract"/"generic"),决定截断长度与转义策略
    """
    if not text:
        return ""
    # 先反转义 HTML 实体(&lt; → <, &amp; → &),再剥标签,避免实体包裹的标签遗漏
    text = html.unescape(text)
    # 剥离 HTML 标签(防 XSS)
    text = re.sub(r'<[^>]+>', '', text)
    # 压缩连续空白为单个空格
    text = re.sub(r'\s+', ' ', text).strip()
    # 标题中转义 Markdown 特殊字符(避免破坏列表/链接格式)
    if field_type == "title":
        for ch in ('[', ']', '(', ')'):
            text = text.replace(ch, '\\' + ch)
        if len(text) > 200:
            text = text[:200] + "..."
    elif field_type == "abstract":
        if len(text) > 300:
            text = text[:300] + "..."
    return text


def sanitize_url(url: str) -> str:
    """校验 URL 协议,仅允许 http/https,拒绝 javascript:/file:等危险协议。"""
    if not url:
        return ""
    url = url.strip()
    # 仅放行 http/https 协议
    if re.match(r'^https?://', url, re.IGNORECASE):
        return url
    return ""


# 源优先级顺序(供 dedup 模块使用,索引越小优先级越高)
SOURCE_PRIORITY = [
    "arxiv_cs_ai", "arxiv_cs_lg", "arxiv_stat_ml",
    "arxiv_qbio_gn", "arxiv_qbio_qm",
    "pubmed", "biorxiv",
    "github_ai", "hn", "reddit_ml", "producthunt",
    "zhihu", "36kr", "nowcoder", "weibo", "baidu",
]
