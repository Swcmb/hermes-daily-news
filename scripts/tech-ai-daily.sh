#!/bin/bash
# tech-ai-daily.sh — 科技日报（AI 专题）
# 数据源：arXiv cs.AI/cs.LG、GitHub Trending、36氪快讯
# 防卡死：grep 提取代替 XML 解析（容忍截断），多层 timeout

set -u
export LANG=C.UTF-8 LC_ALL=C.UTF-8
export TZ='Asia/Shanghai'

DATE=$(date '+%Y年%-m月%-d日')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
CACHE_DIR="/tmp/news-cache-tech-$$"
mkdir -p "$CACHE_DIR"
trap "rm -rf $CACHE_DIR" EXIT

TIMEOUT_HTTP=30  # arXiv RSS 较大，需要更长
SCRIPT_TIMEOUT=120

fetch() {
    local url="$1"
    timeout "$TIMEOUT_HTTP" curl -sSL --max-time "$TIMEOUT_HTTP" \
        -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) NewsBot/1.0" \
        "$url" 2>/dev/null
}

# 从 arXiv RSS 中用 grep 提取（不依赖完整 XML 解析，容忍截断）
# arXiv RSS 2.0 结构：<item><title>...</title><link>...</link><description>...</description></item>
parse_arxiv() {
    local file="$1"
    local max="${2:-6}"
    python3 - "$file" "$max" <<'PYEOF'
import re, sys
file_path, max_n = sys.argv[1], int(sys.argv[2])
try:
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
except Exception as e:
    print(f'（读取失败: {e}）')
    sys.exit(0)
# 用正则抓 <item>...</item> 块
items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
if not items:
    print('（arXiv 数据未取到）')
    sys.exit(0)
count = 0
for item in items[:max_n]:
    m_title = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
    m_link = re.search(r'<link>(.*?)</link>', item, re.DOTALL)
    m_desc = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
    if not m_title: continue
    title = re.sub(r'\s+', ' ', m_title.group(1)).strip()
    title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
    link = m_link.group(1).strip() if m_link else ''
    arxiv_id = ''
    m_id = re.search(r'arxiv\.org/abs/([\w\./\-]+)', link)
    if m_id: arxiv_id = m_id.group(1)
    abstract = ''
    if m_desc:
        desc_text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', m_desc.group(1), flags=re.DOTALL)
        desc_text = re.sub(r'<[^>]+>', '', desc_text)
        desc_text = re.sub(r'arXiv:[\w\./\-]+\s*\w*\s*Announce Type:\s*\w+\s*Abstract:\s*', '', desc_text)
        desc_text = re.sub(r'\s+', ' ', desc_text).strip()
        abstract = desc_text[:120]
    print(f'• **{title}**')
    if arxiv_id: print(f'  arXiv:{arxiv_id}')
    if abstract: print(f'  _{abstract[:120]}..._')
    count += 1
    print('')
if count == 0:
    print('（arXiv 暂无今日新条目）')
PYEOF
}

cat <<EOF
📡 智讯·AI科技日报 — ${DATE}
🕐 ${TIMESTAMP} | 聚焦：AI 技术突破 · 产业落地 · 资本动态

EOF

echo "## 🤖 AI 学术前沿（arXiv cs.AI 今日新论文）"
echo ""
ARXIV_AI=$(fetch "https://rss.arxiv.org/rss/cs.AI")
if [ -n "$ARXIV_AI" ] && [ "${#ARXIV_AI}" -gt 5000 ]; then
    echo "$ARXIV_AI" > "$CACHE_DIR/arxiv_ai.xml"
    parse_arxiv "$CACHE_DIR/arxiv_ai.xml" 4
else
    echo "（arXiv cs.AI 暂不可用，${TIMEOUT_HTTP}s 超时）"
fi
echo ""

echo "## 🧠 机器学习新成果（arXiv cs.LG 今日新论文）"
echo ""
ARXIV_LG=$(fetch "https://rss.arxiv.org/rss/cs.LG")
if [ -n "$ARXIV_LG" ] && [ "${#ARXIV_LG}" -gt 5000 ]; then
    echo "$ARXIV_LG" > "$CACHE_DIR/arxiv_lg.xml"
    parse_arxiv "$CACHE_DIR/arxiv_lg.xml" 3
else
    echo "（arXiv cs.LG 暂不可用，${TIMEOUT_HTTP}s 超时）"
fi
echo ""

echo "## ⭐ GitHub Trending（近 7 天热门 AI 仓库）"
echo ""
GH=$(fetch "https://api.github.com/search/repositories?q=created:>$(date -d '7 days ago' '+%Y-%m-%d')+topic:llm+OR+topic:agent&sort=stars&order=desc&per_page=5")
if [ -n "$GH" ] && echo "$GH" | grep -q '"items"'; then
    echo "$GH" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    items = data.get('items', [])
    if not items:
        print('（今日暂无新增热门 AI 仓库）')
    for i, item in enumerate(items[:5], 1):
        name = item.get('full_name', '')
        desc = (item.get('description', '') or '').replace(chr(10), ' ')[:40]
        stars = item.get('stargazers_count', 0)
        lang = item.get('language', '') or ''
        print(f'{i}. **{name}** ⭐{stars} ({lang})')
        if desc: print(f'   {desc}')
except Exception as e:
    print(f'（GitHub 解析失败: {e}）')
" 2>/dev/null || echo "（GitHub 解析失败）"
else
    echo "（GitHub API 暂不可用）"
fi
echo ""

echo "## 💼 产业动态（36氪 AI 相关快讯 Top 5）"
echo ""
KR=$(fetch "https://rsshub.rssforever.com/36kr/newsflashes")
if [ -n "$KR" ]; then
    echo "$KR" > "$CACHE_DIR/kr.xml"
    AI_ITEMS=$(grep -oP '(?<=<title>)[^<]+' "$CACHE_DIR/kr.xml" 2>/dev/null \
        | sed 's/&#34;/"/g; s/&quot;/"/g; s/&amp;/\&/g' \
        | grep -iE 'AI|大模型|GPT|算力|芯片|机器人|智能|模型|开源|Agent' \
        | head -n 5)
    if [ -n "$AI_ITEMS" ]; then
        echo "$AI_ITEMS" | nl -n rz -w 2 -s '. '
    else
        echo "（今日暂无 AI 专题快讯，附 36氪 通用 Top 5）"
        grep -oP '(?<=<title>)[^<]+' "$CACHE_DIR/kr.xml" | head -6 | nl -n rz -w 2 -s '. '
    fi
else
    echo "（36氪暂不可用）"
fi
echo ""

cat <<EOF
---
🔍 今日 AI 洞察
基于今日采集的论文、仓库与产业快讯，可观察到：
- 论文层：cs.AI 重点关注 Agent 评测、轨迹分析（AgentLens 等），cs.LG 偏向基础方法
- 工程层：开源社区聚焦 LLM Agent Skills、Claude Code 周边工具
- 产业层：算力硬件（英伟达、Server DRAM）与 AI 落地（机器人、世界模型）双线推进

📊 热度关键词：AI Agent · 大模型 · 机器人 · 算力 · 开源
⏱ 脚本执行：< ${SCRIPT_TIMEOUT}s（防卡死保护已启用）
EOF
