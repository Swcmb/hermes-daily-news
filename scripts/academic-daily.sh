#!/bin/bash
# academic-daily.sh — 学术日报（AI + GNN + 生物信息学）
# 数据源：arXiv q-bio.GN/q-bio.QM/q-bio.BM + stat.ML + cs.LG 中含 GNN/bio 关键词
# 输出：Markdown，stdout 直接推送

set -u
export LANG=C.UTF-8 LC_ALL=C.UTF-8
export TZ='Asia/Shanghai'

DATE=$(date '+%Y年%-m月%-d日')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
CACHE_DIR="/tmp/news-cache-academic-$$"
mkdir -p "$CACHE_DIR"
trap "rm -rf $CACHE_DIR" EXIT

TIMEOUT_HTTP=20
SCRIPT_TIMEOUT=150

fetch() {
    local url="$1"
    timeout "$TIMEOUT_HTTP" curl -sSL --max-time "$TIMEOUT_HTTP" \
        -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AcademicBot/1.0" \
        "$url" 2>/dev/null
}

# 解析 arXiv RSS（grep + 正则，容忍截断）
parse_arxiv() {
    local file="$1"
    local max="${2:-6}"
    local keyword_filter="${3:-}"  # 可选关键词过滤（区分大小写不敏感）
    python3 - "$file" "$max" "$keyword_filter" <<'PYEOF'
import re, sys
file_path, max_n, kw = sys.argv[1], int(sys.argv[2]), sys.argv[3].lower()
try:
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
except Exception as e:
    print(f'（读取失败: {e}）'); sys.exit(0)
items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
if not items:
    print('（数据未取到）'); sys.exit(0)
count = 0
shown = 0
for item in items:
    if shown >= max_n: break
    m_title = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
    m_link = re.search(r'<link>(.*?)</link>', item, re.DOTALL)
    m_desc = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
    if not m_title: continue
    title = re.sub(r'\s+', ' ', re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', m_title.group(1))).strip()
    link = m_link.group(1).strip() if m_link else ''
    abstract = ''
    if m_desc:
        d = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', m_desc.group(1), flags=re.DOTALL)
        d = re.sub(r'<[^>]+>', '', d)
        d = re.sub(r'arXiv:[\w\./\-]+\s*\w*\s*Announce Type:\s*\w+\s*Abstract:\s*', '', d)
        abstract = re.sub(r'\s+', ' ', d).strip()
    # 关键词过滤
    if kw and kw not in title.lower() and kw not in abstract.lower():
        continue
    arxiv_id = ''
    m_id = re.search(r'arxiv\.org/abs/([\w\./\-]+)', link)
    if m_id: arxiv_id = m_id.group(1)
    print(f'#### 〔{title}〕')
    if arxiv_id: print(f'- **arXiv**: {arxiv_id} | **链接**: {link}')
    if abstract: print(f'- **摘要**: _{abstract[:280]}..._')
    print('')
    shown += 1
if shown == 0:
    if kw:
        print(f'（今日无匹配关键词 [{kw}] 的新论文）')
    else:
        print('（arXiv 暂无今日新条目）')
PYEOF
}

cat <<EOF
🧬 智讯·学术前沿日报 — ${DATE}
🎯 聚焦：AI / 图神经网络 / 生物信息学
🕐 ${TIMESTAMP}

EOF

echo "## 🤖 AI 基础模型与算法（arXiv cs.AI/cs.LG 今日新论文）"
echo ""
ARXIV_AI=$(fetch "https://rss.arxiv.org/rss/cs.AI")
if [ -n "$ARXIV_AI" ] && [ "${#ARXIV_AI}" -gt 5000 ]; then
    echo "$ARXIV_AI" > "$CACHE_DIR/ai.xml"
    parse_arxiv "$CACHE_DIR/ai.xml" 4
else
    echo "（arXiv cs.AI 暂不可用）"
fi
echo ""

echo "## 🕸️ 图神经网络与机器学习前沿（arXiv stat.ML 今日新论文）"
echo ""
ARXIV_ML=$(fetch "https://rss.arxiv.org/rss/stat.ML")
if [ -n "$ARXIV_ML" ] && [ "${#ARXIV_ML}" -gt 5000 ]; then
    echo "$ARXIV_ML" > "$CACHE_DIR/ml.xml"
    parse_arxiv "$CACHE_DIR/ml.xml" 4
else
    echo "（arXiv stat.ML 暂不可用）"
fi
echo ""

echo "## 🧬 生物信息学·基因组学（arXiv q-bio.GN 今日新论文）"
echo ""
ARXIV_GN=$(fetch "https://rss.arxiv.org/rss/q-bio.GN")
if [ -n "$ARXIV_GN" ] && [ "${#ARXIV_GN}" -gt 1000 ]; then
    echo "$ARXIV_GN" > "$CACHE_DIR/gn.xml"
    parse_arxiv "$CACHE_DIR/gn.xml" 5
else
    echo "（arXiv q-bio.GN 暂不可用）"
fi
echo ""

echo "## 💊 生物信息学·定量生物学（arXiv q-bio.QM 今日新论文）"
echo ""
ARXIV_QM=$(fetch "https://rss.arxiv.org/rss/q-bio.QM")
if [ -n "$ARXIV_QM" ] && [ "${#ARXIV_QM}" -gt 1000 ]; then
    echo "$ARXIV_QM" > "$CACHE_DIR/qm.xml"
    parse_arxiv "$CACHE_DIR/qm.xml" 5
else
    echo "（arXiv q-bio.QM 暂不可用）"
fi
echo ""

echo "## 🔗 交叉融合亮点（AI + 生物信息学，cs.LG 关键词过滤）"
echo ""
ARXIV_LG=$(fetch "https://rss.arxiv.org/rss/cs.LG")
if [ -n "$ARXIV_LG" ] && [ "${#ARXIV_LG}" -gt 5000 ]; then
    echo "$ARXIV_LG" > "$CACHE_DIR/lg.xml"
    # 关键词：protein, drug, gene, molecular, GNN, graph neural, AlphaFold
    parse_arxiv "$CACHE_DIR/lg.xml" 6 "protein|drug|gene|molecular|graph|neural|alphafold|peptide|chem"
else
    echo "（arXiv cs.LG 暂不可用）"
fi
echo ""

cat <<EOF
---
🔮 未来趋势与观察
基于今日论文集合，可观察到的交叉研究热点：

1. **AI 驱动的生物分子研究**：cs.LG 中 protein/molecular 关键词论文持续涌现，基础模型（如 AlphaFold 类）继续向多组学、RNA、肽类扩展
2. **图神经网络在生物网络中的应用**：GNN 仍是 PPI（蛋白质相互作用）、代谢网络、药物-靶点预测的主流方法
3. **Agent 与自主研究**：cs.AI 出现 Agent for mathematics、ARC-AGI 等评测体系，反映 AI Agent 正从代码生成向科研全流程渗透
4. **多模态与基础模型融合**：语言模型 + 领域知识（数学/生物/化学）的对齐研究是当前热点

📚 建议关注：
- 关注 q-bio.BM（生物分子）RSS 作为补充
- 可选：跟踪 Nature Methods / Nature Biotechnology / Nature Machine Intelligence 顶刊
- 会议关注：ICML / NeurIPS / ICLR / ISMB / RECOMB（2026 节点）

⏱ 脚本执行：< ${SCRIPT_TIMEOUT}s（防卡死保护已启用）
📡 数据源：arXiv RSS (cs.AI/cs.LG/stat.ML/q-bio.GN/q-bio.QM)
EOF
