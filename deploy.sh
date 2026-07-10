#!/bin/bash
# deploy.sh — 智讯日报系统部署脚本
# 设计意图:自动化备份→拷贝→渲染 prompt→输出 cron 命令,不自动执行 cron 更新
# 用法:bash deploy.sh [--run-tests] [--target-dir ~/.hermes/scripts/daily-news]

set -eu
export LANG=C.UTF-8 LC_ALL=C.UTF-8

# 参数解析
RUN_TESTS=false
TARGET_DIR="${HOME}/.hermes/scripts/daily-news"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --run-tests) RUN_TESTS=true; shift ;;
        --target-dir) TARGET_DIR="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# 定位项目根
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

echo "=== 智讯日报系统部署 ==="
echo "项目根: $PROJECT_ROOT"
echo "目标目录: $TARGET_DIR"
echo ""

# 步骤 0:可选 pytest 验证
if [ "$RUN_TESTS" = true ]; then
    echo "--- 步骤 0:运行 pytest 验证 ---"
    cd "$PROJECT_ROOT/tests"
    if python3 -m pytest -v --tb=short 2>&1 | tail -5; then
        echo "pytest 验证通过"
    else
        echo "错误:pytest 验证失败,部署中止"
        exit 1
    fi
    cd "$PROJECT_ROOT"
    echo ""
fi

# 步骤 1:备份旧脚本(如果目标目录已存在)
if [ -d "$TARGET_DIR" ]; then
    BACKUP_DIR="${TARGET_DIR}.bak.$(date +%Y%m%d%H%M%S)"
    echo "--- 步骤 1:备份旧脚本到 $BACKUP_DIR ---"
    cp -r "$TARGET_DIR" "$BACKUP_DIR"
    echo "备份完成"
else
    echo "--- 步骤 1:目标目录不存在,跳过备份 ---"
fi
echo ""

# 步骤 2:拷贝新文件
echo "--- 步骤 2:拷贝新文件到 $TARGET_DIR ---"
mkdir -p "$TARGET_DIR"
# 拷贝各子目录
for dir in scripts lib config skill; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        cp -r "$PROJECT_ROOT/$dir" "$TARGET_DIR/"
    fi
done
# 拷贝 deploy.sh 自身
cp "$PROJECT_ROOT/deploy.sh" "$TARGET_DIR/" 2>/dev/null || true
echo "拷贝完成"
echo ""

# 步骤 3:渲染 agent prompt 模板
echo "--- 步骤 3:渲染 agent prompt 模板 ---"
# shellcheck source=config/config.sh
source "$PROJECT_ROOT/config/config.sh"

render_prompt() {
    local news_type="$1"
    local type_upper
    type_upper=$(echo "$news_type" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
    cat <<PROMPT
你是智讯日报主编。请执行以下步骤生成今日 ${news_type} 日报:

1. 运行命令:python3 ~/.hermes/scripts/daily-news/lib/fetch_worker.py --type ${news_type}
   (fetch_worker 会自行加载 config.sh 配置,无需额外 source)
2. 读取命令输出的 JSON 数据(包含各源条目)
3. 将所有英文标题与摘要翻译为简体中文(保留专业术语如 LLM/Agent/GAN 的原文)
4. 按以下格式输出 Markdown 日报:
   - 每个数据源作为一个 ## 分节
   - 每条目:编号 + **中文标题** + 摘要(意译,限 150 字) + 原始链接
   - 结尾附今日洞察(基于数据归纳 3 条趋势)
5. 用今天的日期作为文件名标识:运行 date +%Y-%m-%d 获取当天日期(记为 DATE),
   将 Markdown 写入 /tmp/news-${news_type}-\${DATE}.md
6. 执行推送:hermes send -f /tmp/news-${news_type}-\${DATE}.md -t ${QQ_TARGET}
7. 推送成功后创建标记文件:touch /tmp/news-${news_type}-\${DATE}.done

翻译规范:标题必译,摘要意译,专业术语保留英文,人名保留英文。
PROMPT
}

TECH_AI_PROMPT=$(render_prompt "tech-ai")
ACADEMIC_PROMPT=$(render_prompt "academic")

echo "prompt 模板已渲染(QQ_TARGET=${QQ_TARGET})"
echo ""

# 步骤 4:输出 cron 更新命令
echo "--- 步骤 4:请执行以下 cron 命令(需手动确认) ---"
echo ""
echo "# 1. 查询现有任务 ID:"
echo "   hermes cron list | grep daily-news"
echo ""
echo "# 2. 更新综合新闻(no-agent 模式):"
echo "   hermes cron update <id> --script daily-news/scripts/comprehensive.sh --no_agent=true"
echo ""
echo "# 3. 更新 tech-ai(agent 模式,需粘贴 prompt):"
echo "   hermes cron update <id> --no_agent=false --script='' --prompt '<见下方 TEH_AI_PROMPT>' --skill daily-news-editor"
echo ""
echo "# 4. 更新 academic(agent 模式):"
echo "   hermes cron update <id> --no_agent=false --script='' --prompt '<见下方 ACADEMIC_PROMPT>' --skill daily-news-editor"
echo ""
echo "# 5.(可选)创建 fallback cron:"
echo "   hermes cron create --name daily-tech-ai-fallback --schedule '15 12 * * *' --script daily-news/scripts/tech-ai-fallback.sh --no_agent=true"
echo "   hermes cron create --name daily-academic-fallback --schedule '15 18 * * *' --script daily-news/scripts/academic-fallback.sh --no_agent=true"
echo ""

# 将 prompt 写入文件供用户复制
PROMPT_FILE="/tmp/news-prompts-$(date +%Y%m%d).txt"
{
    echo "===== TECH_AI PROMPT ====="
    echo "$TECH_AI_PROMPT"
    echo ""
    echo "===== ACADEMIC PROMPT ====="
    echo "$ACADEMIC_PROMPT"
} > "$PROMPT_FILE"
echo "完整 prompt 已写入: $PROMPT_FILE (供复制到 cron 命令中)"
echo ""

echo "=== 部署完成 ==="
echo "下一步:"
echo "  1. 执行上述 cron 命令更新调度任务"
echo "  2. 手动测试:bash $TARGET_DIR/scripts/comprehensive.sh"
echo "  3. 检查日志:tail -f ~/.hermes/logs/news-*.log"
