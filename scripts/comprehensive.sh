#!/bin/bash
# comprehensive.sh — 综合新闻日报(no-agent 模式,完整链路)
# 设计意图:Shell 全权负责 抓取→格式化→推送,无需 LLM 参与,稳定性最高
# 数据源:知乎·36氪·牛客·微博·百度(全中文,无需翻译)

set -u
export LANG=C.UTF-8 LC_ALL=C.UTF-8
export TZ='Asia/Shanghai'

# 定位项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 加载公共库
# shellcheck source=../lib/common.sh
source "$PROJECT_ROOT/lib/common.sh"
load_config

# 临时文件管理
trap cleanup EXIT
MARKDOWN_FILE="/tmp/news-comprehensive-$(date +%Y-%m-%d).md"
register_tmpfile MARKDOWN_FILE comprehensive

# 执行抓取 + 格式化(fetch_worker 输出 JSON → format_markdown 转中文 Markdown)
JSON_OUTPUT=$(python3 "$PROJECT_ROOT/lib/fetch_worker.py" --type comprehensive 2>/dev/null)
FETCH_EXIT=$?

if [ -z "$JSON_OUTPUT" ]; then
    echo "📰 智讯·综合新闻日报 — ${DATE}"
    echo "🕐 ${TIMESTAMP}"
    echo ""
    echo "（数据采集服务异常，请检查日志）"
    echo ""
    echo "---"
    echo "⏱ 数据采集时间：${TIMESTAMP}"
    log_error "comprehensive" "fetch_worker" "crash" "" "" "stdout 为空"
    exit 2
fi

# JSON → Markdown
echo "$JSON_OUTPUT" | python3 "$PROJECT_ROOT/lib/format_markdown.py" comprehensive > "$MARKDOWN_FILE"

if [ ! -s "$MARKDOWN_FILE" ]; then
    log_error "comprehensive" "format_markdown" "fail" "" "" "Markdown 文件为空"
    exit 2
fi

# 推送到 QQ
send_to_qq "$QQ_TARGET" "$MARKDOWN_FILE"
PUSH_EXIT=$?

# 日志记录
if [ $PUSH_EXIT -eq 0 ]; then
    log_info "comprehensive" "push" "ok"
else
    log_error "comprehensive" "push" "fail" "" "" "hermes send 退出码 $PUSH_EXIT"
fi

exit $PUSH_EXIT
