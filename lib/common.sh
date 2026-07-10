#!/bin/bash
# common.sh — 智讯日报 Shell 公共函数库
# 设计意图:消除三脚本间重复代码,统一配置加载/日志/格式化/推送
# 依赖:config.sh(由 load_config 加载)

# 防止重复 source
[ -n "${_COMMON_SH_LOADED:-}" ] && return 0
_COMMON_SH_LOADED=1

# 定位项目根目录(基于本文件路径)
NEWS_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 加载配置并导出环境变量
load_config() {
    local config_sh="${NEWS_PROJECT_ROOT}/config/config.sh"
    if [ ! -f "$config_sh" ]; then
        echo "错误:配置文件不存在 $config_sh" >&2
        return 1
    fi
    # shellcheck disable=SC1090
    source "$config_sh"
    # 生成时间戳(load_config 后调用,确保时区已设置)
    export TZ='Asia/Shanghai'
    TIMESTAMP="$(date +%Y-%m-%dT%H:%M:%S%z)"
    DATE="$(date +%Y年%-m月%-d日)"
    export TIMESTAMP DATE
    # 确保日志目录存在
    mkdir -p "$LOG_DIR" 2>/dev/null || true
}

# 生成日志文件路径
# 参数:$1=日报类型(comprehensive/tech-ai/academic)
_log_file() {
    local news_type="$1"
    local today
    today="$(date +%Y-%m-%d)"
    echo "${LOG_DIR}/news-${news_type}-${today}.log"
}

# 结构化日志写入
# 参数:$1=级别 $2=日报类型 $3=源 $4=状态 $5=耗时ms $6=条数 $7=错误信息(可选)
_log_write() {
    local level="$1" news_type="$2" source="$3" status="$4"
    local elapsed="${5:-}" items="${6:-}" error="${7:-}"
    local ts
    ts="$(date +%Y-%m-%dT%H:%M:%S%z)"
    local msg="${ts} ${level}  ${news_type} ${source} ${status}"
    [ -n "$elapsed" ] && msg+=" ${elapsed}ms"
    [ -n "$items" ] && msg+=" ${items}items"
    [ -n "$error" ] && msg+=" \"${error}\""
    echo "$msg" >> "$(_log_file "$news_type")" 2>/dev/null || true
}

log_info()  { _log_write "INFO"  "$@"; }
log_warn()  { _log_write "WARN"  "$@"; }
log_error() { _log_write "ERROR" "$@"; }

# 格式化:日报标题头
# 参数:$1=emoji $2=日报名 $3=日期 $4=时间戳
format_header() {
    local emoji="$1" name="$2" date="$3" ts="$4"
    echo "${emoji} 智讯·${name}日报 — ${date}"
    echo "🕐 ${ts}"
    echo ""
}

# 格式化:分节标题
# 参数:$1=emoji $2=分节名 $3=副标题
format_section() {
    local emoji="$1" name="$2" subtitle="$3"
    echo "## ${emoji} ${name}"
    [ -n "$subtitle" ] && echo "（${subtitle}）"
    echo ""
}

# 格式化:编号列表项
# 参数:$1=序号 $2=标题(Markdown) $3=描述(可选)
format_listitem() {
    local idx="$1" title="$2" desc="$3"
    echo "${idx}. ${title}"
    [ -n "$desc" ] && echo "   ${desc}"
}

# 格式化:结尾
# 参数:$1=脚本超时阈值 $2=时间戳
format_footer() {
    local timeout="$1" ts="$2"
    echo ""
    echo "---"
    echo "⏱ 脚本执行：< ${timeout}s（防卡死保护已启用）"
    echo "🕐 数据采集时间：${ts}"
}

# 推送 Markdown 到 QQ Bot
# 参数:$1=目标(qqbot:XXX) $2=Markdown 文件路径
send_to_qq() {
    local target="$1" md_file="$2"
    if [ ! -f "$md_file" ]; then
        echo "错误:Markdown 文件不存在 $md_file" >&2
        return 1
    fi
    hermes send -f "$md_file" -t "$target"
}

# 临时文件管理(供脚本 trap EXIT 调用)
# 用法: register_tmpfile 变量名 → 赋值文件路径;cleanup 统一删除
_NEWS_TMPFILES=()
register_tmpfile() {
    local -n ref="$1"
    ref="$(mktemp /tmp/news-${2:-tmp}.XXXXXX)"
    _NEWS_TMPFILES+=("$ref")
}

cleanup() {
    for f in "${_NEWS_TMPFILES[@]}"; do
        [ -f "$f" ] && rm -f "$f" 2>/dev/null || true
    done
}
