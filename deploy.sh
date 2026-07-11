#!/bin/bash
# deploy.sh — 智讯日报部署脚本
# 设计意图:将项目文件拷贝到 ~/.hermes/scripts/daily-news/ 并渲染 agent prompt
set -eu
export LANG=C.UTF-8 LC_ALL=C.UTF-8
export TZ='Asia/Shanghai'

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.hermes/scripts/daily-news"

# 步骤 1:创建目标目录
echo "=== 智讯日报部署 ==="
mkdir -p "$TARGET_DIR"/{config,lib/parsers,scripts,skill,tests}
echo "目标目录: $TARGET_DIR"

# 步骤 2:拷贝项目文件
echo "--- 步骤 2:拷贝项目文件 ---"
for dir in config lib scripts skill tests; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        cp -r "$PROJECT_ROOT/$dir" "$TARGET_DIR/"
    fi
done
cp "$PROJECT_ROOT/deploy.sh" "$TARGET_DIR/" 2>/dev/null || true
echo "拷贝完成"

# 步骤 3:渲染 agent prompt 模板
source "$PROJECT_ROOT/config/config.sh"

render_tech_ai_prompt() {
    cat <<'PROMPT'
你是智讯日报主编。请执行以下步骤生成今日 AI 科技日报:

1. 运行命令:python3 ~/.hermes/scripts/daily-news/lib/fetch_worker.py --type tech-ai
2. 读取命令输出的 JSON 数据,按以下 3 个分析维度分类整理:
   - 论文突破:arXiv cs.AI/cs.LG 中有方法论创新或实验突破的论文
   - 开源项目:GitHub/HN/ProductHunt 中有实质贡献的 AI 项目
   - 行业动态:36kr/TechCrunch 中的产品发布、融资、标准动态
3. 将所有英文标题与摘要翻译为简体中文
4. 按以下格式输出 Markdown 日报:
   - 每个维度作为一个 ## 分节
   - 每条目按重要性排序
   - 收录标准:只收录有实质贡献的论文/项目
   - 结尾附今日趋势点评(2-3句)
5. 将 Markdown 写入 /tmp/news-tech-ai-${DATE}.md
6. 推送:hermes send -f /tmp/news-tech-ai-${DATE}.md -t ${QQ_TARGET}
7. 创建标记:touch /tmp/news-tech-ai-${DATE}.done
PROMPT
}

render_academic_prompt() {
    cat <<'PROMPT'
你是智讯日报主编。请执行以下步骤生成今日学术前沿日报:

1. 运行命令:python3 ~/.hermes/scripts/daily-news/lib/fetch_worker.py --type academic
2. 读取 JSON 数据,按以下 4 个分析维度分类整理:
   - 方法论创新:新模型/新算法/新训练方法
   - 实验突破:SOTA 或显著提升
   - 可复现性:开源代码/数据集/模型(优先收录)
   - 跨学科应用:AI 与基因组学/定量生物学交叉
3. 翻译英文为简体中文
4. 输出 Markdown 日报,每条附 arxiv_id/DOI/PMID
5. 写入 /tmp/news-academic-${DATE}.md
6. 推送:hermes send -f /tmp/news-academic-${DATE}.md -t ${QQ_TARGET}
7. 创建标记:touch /tmp/news-academic-${DATE}.done
PROMPT
}

TECH_AI_PROMPT=$(render_tech_ai_prompt | sed "s/\${QQ_TARGET}/${QQ_TARGET}/")
ACADEMIC_PROMPT=$(render_academic_prompt | sed "s/\${QQ_TARGET}/${QQ_TARGET}/")

echo "prompt 模板已渲染"
echo "=== 部署完成 ==="
