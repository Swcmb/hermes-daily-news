#!/bin/bash
# tech-ai-fallback.sh — tech-ai LLM 失败兜底
# 设计意图:agent 模式 LLM 翻译/推送失败时,延迟 15 分钟由本脚本英文兜底推送
# 触发条件:检查 .done 标记文件,存在则退出(LLM 已成功推送),不存在则执行兜底

set -u
export LANG=C.UTF-8 LC_ALL=C.UTF-8
export TZ='Asia/Shanghai'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../lib/common.sh
source "$PROJECT_ROOT/lib/common.sh"
load_config

trap cleanup EXIT
TODAY=$(date +%Y-%m-%d)
DONE_MARKER="/tmp/news-tech-ai-${TODAY}.done"
MARKDOWN_FILE="/tmp/news-tech-ai-${TODAY}.md"
register_tmpfile MARKDOWN_FILE tech-ai

# 检查 .done 标记:LLM 已成功推送则退出
if [ -f "$DONE_MARKER" ]; then
    log_info "tech-ai" "fallback" "skip" "" "" "LLM 已推送,.done 标记存在"
    exit 0
fi

log_warn "tech-ai" "fallback" "trigger" "" "" "LLM 未推送,启动英文兜底"

# 调用 tech-ai.sh 逻辑获取英文 Markdown
bash "$SCRIPT_DIR/tech-ai.sh" > "$MARKDOWN_FILE" 2>/dev/null
if [ ! -s "$MARKDOWN_FILE" ]; then
    log_error "tech-ai" "fallback" "fail" "" "" "Markdown 文件为空"
    exit 2
fi

# 在文件头部插入翻译不可用提示
TEMP_HEADER=$(mktemp /tmp/news-tech-ai-header.XXXXXX)
{
    echo "> ⚠️ 翻译暂不可用，以下为英文原文（LLM agent 翻译失败兜底）"
    echo ""
    cat "$MARKDOWN_FILE"
} > "$TEMP_HEADER"
mv "$TEMP_HEADER" "$MARKDOWN_FILE"

# 推送
send_to_qq "$QQ_TARGET" "$MARKDOWN_FILE"
PUSH_EXIT=$?

if [ $PUSH_EXIT -eq 0 ]; then
    # 创建 .done 标记,避免重复推送
    touch "$DONE_MARKER"
    log_info "tech-ai" "fallback" "ok"
else
    log_error "tech-ai" "fallback" "fail" "" "" "推送失败,退出码 $PUSH_EXIT"
fi

exit $PUSH_EXIT
