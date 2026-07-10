#!/bin/bash
# academic.sh — academic 手动测试入口
# 设计意图:抓取+英文格式化,输出到 stdout,不推送(供手动测试和 fallback 调用)
# agent 模式下 LLM 直接执行 fetch_worker,此脚本仅用于测试与兜底

set -u
export LANG=C.UTF-8 LC_ALL=C.UTF-8
export TZ='Asia/Shanghai'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$PROJECT_ROOT/lib/common.sh"
load_config

# 抓取 + 格式化(英文,供 LLM 翻译或 fallback 使用)
JSON_OUTPUT=$(python3 "$PROJECT_ROOT/lib/fetch_worker.py" --type academic 2>/dev/null)
FETCH_EXIT=$?

if [ -z "$JSON_OUTPUT" ]; then
    echo "🧬 智讯·学术前沿日报 — ${DATE}"
    echo "（数据采集服务异常，请检查日志）"
    exit 2
fi

# JSON → Markdown(输出到 stdout,不推送)
echo "$JSON_OUTPUT" | python3 "$PROJECT_ROOT/lib/format_markdown.py" academic
exit $FETCH_EXIT
