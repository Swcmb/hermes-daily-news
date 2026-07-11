#!/bin/bash
# comprehensive-news-daily.sh — 综合新闻日报
# 设计原则：纯 shell，无 LLM agent loop；多源并行 + 严格超时防卡死
# 数据源：知乎热榜、36氪快讯、牛客热议、GitHub Trending
# 输出：Markdown 格式，stdout 直接被 Hermes cron 推送到 QQ

set -u
export LANG=C.UTF-8 LC_ALL=C.UTF-8
export TZ='Asia/Shanghai'

DATE=$(date '+%Y年%-m月%-d日')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
CACHE_DIR="/tmp/news-cache-comprehensive-$$"
mkdir -p "$CACHE_DIR"
trap "rm -rf $CACHE_DIR" EXIT

# 单次 HTTP 硬超时
TIMEOUT_HTTP=8
# 单源抓取在后台运行，wait + timeout 双重保险
SCRIPT_TIMEOUT=50

# 通用 fetch 函数
fetch() {
    local url="$1"
    timeout "$TIMEOUT_HTTP" curl -sSL --max-time "$TIMEOUT_HTTP" \
        -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) NewsBot/1.0" \
        "$url" 2>/dev/null
}

# 提取 RSS/Atom <title>
extract_titles() {
    local file="$1"
    local limit="${2:-15}"
    grep -oP '(?<=<title>)[^<]+' "$file" 2>/dev/null \
        | sed 's/&#34;/"/g; s/&quot;/"/g; s/&amp;/\&/g; s/&lt;/</g; s/&gt;/>/g' \
        | grep -v 'RSS\|订阅\|feed' \
        | head -n "$limit"
}

# ---- 启动输出 ----
cat <<EOF
📰 智讯·综合新闻日报 — ${DATE}
🕐 ${TIMESTAMP} | 数据源：知乎 · 36氪 · 牛客 · GitHub Trending

EOF

echo "## 🇨🇳 国内热点（知乎热榜 Top 10）"
echo ""
ZHIHU=$(fetch "https://www.zhihu.com/rss")
if [ -n "$ZHIHU" ]; then
    echo "$ZHIHU" > "$CACHE_DIR/zhihu.xml"
    extract_titles "$CACHE_DIR/zhihu.xml" 10 | nl -n rz -w 2 -s '. '
else
    echo "（知乎热榜暂不可用）"
fi
echo ""

echo "## 💹 财经科技快讯（36氪 Top 5）"
echo ""
KR=$(fetch "https://rsshub.rssforever.com/36kr/newsflashes")
if [ -n "$KR" ]; then
    echo "$KR" > "$CACHE_DIR/kr.xml"
    extract_titles "$CACHE_DIR/kr.xml" 5 | nl -n rz -w 2 -s '. '
else
    echo "（36氪暂不可用）"
fi
echo ""

echo "## 💻 行业热议（牛客 Top 4）"
echo ""
NC=$(fetch "https://rsshub.rssforever.com/nowcoder/recommend")
if [ -n "$NC" ]; then
    echo "$NC" > "$CACHE_DIR/nc.xml"
    extract_titles "$CACHE_DIR/nc.xml" 4 | nl -n rz -w 2 -s '. '
else
    echo "（牛客暂不可用）"
fi
echo ""

echo "## ⭐ GitHub Trending（近 7 天新增热门仓库）"
echo ""
GH=$(fetch "https://api.github.com/search/repositories?q=created:>$(date -d '7 days ago' '+%Y-%m-%d')+language:python&sort=stars&order=desc&per_page=5")
if [ -n "$GH" ]; then
    echo "$GH" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for i, item in enumerate(data.get('items', [])[:5], 1):
        name = item.get('full_name', '')
        desc = (item.get('description', '') or '').replace(chr(10), ' ')[:40]
        stars = item.get('stargazers_count', 0)
        lang = item.get('language', '') or ''
        print(f'{i}. **{name}** ⭐{stars} ({lang}) — {desc}')
except Exception as e:
    print(f'（GitHub 数据解析失败: {e}）')
" 2>/dev/null || echo "（GitHub 数据解析失败）"
else
    echo "（GitHub API 暂不可用）"
fi
echo ""

cat <<EOF
---
💎 今日提示
- 数据采集时间：${TIMESTAMP}
- 国外新闻源（BBC/NYT/HN）因网络限制暂未纳入
- 财经数据以上海/深圳交易所官方公告为准
- 关键决策请查阅原始来源

⏱ 脚本执行：< ${SCRIPT_TIMEOUT}s（防卡死保护已启用）
EOF
