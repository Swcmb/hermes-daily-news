---
name: daily-news-editor
description: 智讯日报主编 - 每日自动推送综合新闻/AI科技/学术三大日报到 QQ bot（v2.1 Shell+Python 混合架构）
version: 2.1.0
author: 智讯日报主编 Agent
---

# 智讯日报主编 Skill

## 功能

每日自动从 18 个数据源采集并推送三大类日报到用户 QQ：

| 日报类型 | 推送时间 | 模式 | 数据源 |
|---------|---------|------|--------|
| 📰 综合新闻日报 | 每日 08:00 | no-agent（纯 Shell） | 知乎热榜 · 36氪快讯 · 牛客热议 · 微博热搜 · 百度热搜 |
| 📡 AI 科技日报 | 每日 12:00 | agent（LLM 翻译） | arXiv cs.AI/cs.LG · GitHub · Hacker News · Product Hunt · Reddit r/ML · 36氪 AI · TechCrunch AI |
| 🧬 学术日报 | 每日 18:00 | agent（LLM 翻译） | arXiv cs.AI/cs.LG/stat.ML/q-bio.GN/q-bio.QM · PubMed · bioRxiv |

## 设计原则

- **中文优先**：所有推送内容必须为简体中文。英文源（arXiv/GitHub/HN/Reddit/ProductHunt/PubMed/bioRxiv/TechCrunch）的标题和摘要必须翻译后呈现。用户明确要求"用中文"时此规则强制执行
- **agent 模式负责英文源翻译**：tech-ai 与 academic 日报默认走 agent 模式（no_agent=false），由 LLM 负责抓取数据、翻译为中文、格式化并推送
- **no-agent 模式负责中文源**：comprehensive 日报数据源（知乎/36氪/牛客/微博/百度）本身为中文，Shell 脚本全权处理，避免 LLM agent loop 卡死，稳定性最高
- **并行抓取 + 跨脚本缓存**：fetch_worker.py 用 ThreadPoolExecutor(4线程) 并行抓取，arXiv 缓存 8h TTL 供 tech-ai 与 academic 复用
- **失败兜底**：单源失败不影响其他源；agent 模式 LLM 失败时由 fallback cron（延迟 15 分钟）英文兜底推送

## 分析维度

### tech-ai 日报（3 维度）

- 📊 **论文突破**：arXiv cs.AI/cs.LG 中有方法论创新或实验突破的论文
- 💻 **开源项目**：GitHub/HN/ProductHunt 中有实质贡献的 AI 项目
- 📰 **行业动态**：36kr/TechCrunch 中的产品发布、融资、标准动态

### academic 日报（4 维度）

- 📊 **方法论创新**：提出新模型/新算法/新训练方法的论文
- 🧪 **实验突破**：在公开数据集上取得 SOTA 或显著提升的论文
- 🔬 **可复现性**：开源代码/数据集/预训练模型的论文（优先收录）
- 🌐 **跨学科应用**：AI 与基因组学/定量生物学/医学交叉的论文

## 收录标准（报告门槛）

### 应收录

- 提出新模型/算法/训练方法的论文
- 在公开数据集取得 SOTA 的论文
- 开源代码/数据集的论文（优先）
- 获得高社区关注（stars>100/points>50）的项目
- 重要产品发布/融资事件/标准动态

### 应省略

- 增量改进（如已有方法的微小变体）
- 自我重复（同一团队相似工作）
- 营销性质的"新闻"
- 无法验证来源的传闻

## 指导原则

- **重相关性而非完整性**：省略琐碎或常规变更，聚焦有实质影响的内容
- **基于证据不推测**：每条陈述基于 fetch_worker 返回的数据，不臆测趋势
- **每条附来源**：所有条目必须附 arxiv_id/repo URL/新闻链接作为证据
- **趋势点评基于数据**：结尾趋势归纳必须从当日数据中提取，不泛泛而谈

## 执行规范（agent 模式必读）

当以 agent 模式执行 tech-ai 或 academic 日报时，严格按以下 5 步执行：

### 步骤 1：调用 fetch_worker 获取数据

```bash
python3 ~/.hermes/scripts/daily-news/lib/fetch_worker.py --type tech-ai
# 或 --type academic
```

- fetch_worker 会自行加载 config.sh 配置，无需额外 source
- 输出为 JSON 数组到 stdout，每个元素是一个源的抓取结果

### 步骤 2：读取并解析 JSON

JSON 结构示例：
```json
[
  {
    "source": "arxiv_cs_ai",
    "source_type": "arxiv",
    "status": "ok",
    "item_count": 6,
    "cache_hit": false,
    "elapsed_ms": 3200,
    "items": [
      {
        "title": "Paper Title Here",
        "url": "https://arxiv.org/abs/2026.12345",
        "abstract": "First 200 chars of abstract...",
        "meta": {"arxiv_id": "2026.12345", "lang": "en"}
      }
    ]
  }
]
```

- `status` 为 `ok`/`cache_hit` 的源有数据；为 `fail`/`empty` 的源跳过
- 对 `fail` 源显示"该源暂不可用"

### 步骤 3：翻译英文标题与摘要为中文

**翻译规范**：
- **标题必译**：所有英文标题必须翻译为简体中文
- **摘要意译**：摘要用流畅中文意译，限 150 字以内，保留核心观点
- **专业术语保留英文**：LLM、Agent、GAN、Transformer、BERT、GNN、CNN、RNN、LSTM、Diffusion、RLHF、RAG、MoE、ViT、CLIP、BLEU、ROUGE、F1、AUC 等通用术语保留英文原文
- **人名保留英文**：作者姓名保留英文原文
- **论文 ID 保留**：arxiv_id、DOI、PMID 等标识符保留原样

### 步骤 4：按 Markdown 格式输出日报

格式模板：
```markdown
📡 智讯·AI科技日报 — 2026年7月10日
🕐 2026-07-10T12:00:00+08:00

## 📊 arXiv cs.AI 热门论文

1. **中文标题**
   摘要内容（意译，限150字）...
   🔗 https://arxiv.org/abs/2026.12345

2. ...

## 💻 GitHub AI 趋势仓库

1. **仓库名**
   描述...
   🔗 https://github.com/owner/repo ★ 1234

## 📈 今日趋势点评

1. 趋势一：基于数据的归纳...
2. 趋势二：...
3. 趋势三：...

---
⏱ 数据采集时间：2026-07-10T12:00:00+08:00 | 智讯日报 v2.1
```

- 每个数据源作为一个 `##` 分节，带 emoji 和中文章节名
- 每条目：编号 + **中文标题** + 摘要 + 原始链接
- tech-ai 结尾附"📈 今日趋势点评"（2-3 句，基于数据归纳）
- academic 结尾附"📈 今日趋势归纳"（3 条趋势方向）
- comprehensive 结尾附"📈 今日趋势"（零 LLM 消耗，词频统计自动生成）

### 步骤 5：推送并创建标记

```bash
# 获取当天日期
DATE=$(date +%Y-%m-%d)

# 将 Markdown 写入文件（文件名含日期确保唯一）
# 写入 /tmp/news-tech-ai-${DATE}.md

# 推送到 QQ
hermes send -f /tmp/news-tech-ai-${DATE}.md -t ${QQ_TARGET}

# 推送成功后创建标记文件（供 fallback cron 检测）
touch /tmp/news-tech-ai-${DATE}.done
```

**`.done` 标记的作用**：fallback cron 在 12:15（tech-ai）或 18:15（academic）检查该标记，若存在则跳过（说明 LLM 已成功推送），若不存在则触发英文兜底推送。

## 关键路径

- 脚本目录：`~/.hermes/scripts/daily-news/`
  - `scripts/comprehensive.sh` - 综合新闻（no-agent，Shell 全权处理）
  - `scripts/tech-ai.sh` - tech-ai 手动测试入口（抓取+英文格式化到 stdout）
  - `scripts/tech-ai-fallback.sh` - tech-ai LLM 失败英文兜底
  - `scripts/academic.sh` - academic 手动测试入口
  - `scripts/academic-fallback.sh` - academic LLM 失败英文兜底
- 核心库：`~/.hermes/scripts/daily-news/lib/`
  - `fetch_worker.py` - 并行抓取入口（agent 模式由 LLM 调用）
  - `format_markdown.py` - JSON → 中文 Markdown（no-agent 模式由 Shell 调用）
  - `common.sh` - Shell 公共库（配置/日志/格式化/推送）
- 配置：`~/.hermes/scripts/daily-news/config/config.sh`
- 日志：`~/.hermes/logs/news-{type}-{date}.log`
- 缓存：`/tmp/hermes-news-cache/`（sha1(source_name:url) 为 key，隔离同 URL 不同 parser；TTL 按源类型区分）

## 数据源详情

### comprehensive（中文源，no-agent 模式）

| 源 | URL | 条数 |
|----|-----|------|
| 知乎热榜 | zhihu.com/rss | 10 |
| 36氪快讯 | rsshub.rssforever.com/36kr/newsflashes | 10 |
| 牛客推荐 | rsshub.rssforever.com/nowcoder/recommend | 8 |
| 微博热搜 | rsshub.rssforever.com/weibo/search/hot | 10 |
| 百度热搜 | rsshub.rssforever.com/baidu/topwords | 10 |

### tech-ai（英文源 + 中文行业动态，agent 模式 LLM 翻译）

| 源 | URL | 条数 | 说明 |
|----|-----|------|------|
| arXiv cs.AI | rss.arxiv.org/rss/cs.AI | 6 | 论文突破维度 |
| arXiv cs.LG | rss.arxiv.org/rss/cs.LG | 6 | 论文突破维度 |
| GitHub AI | api.github.com/search/repositories（topic:llm+OR+topic:agent） | 8 | 开源项目维度 |
| Hacker News | hn.algolia.com/api/v1/search?tags=front_page | 10 | 开源项目维度 |
| Product Hunt | producthunt.com/feed | 6 | 开源项目维度 |
| Reddit r/ML | reddit.com/r/MachineLearning/top.json?t=day | 6 | 开源项目维度 |
| 36氪 AI | rsshub.rssforever.com/36kr/newsflashes | 6 | 行业动态维度（AI 关键词过滤） |
| TechCrunch AI | techcrunch.com/category/artificial-intelligence/feed | 6 | 行业动态维度 |

### academic（英文源，agent 模式 LLM 翻译）

| 源 | URL | 条数 |
|----|-----|------|
| arXiv cs.AI | rss.arxiv.org/rss/cs.AI | 6 |
| arXiv cs.LG | rss.arxiv.org/rss/cs.LG | 6 |
| arXiv stat.ML | rss.arxiv.org/rss/stat.ML | 6 |
| arXiv q-bio.GN | rss.arxiv.org/rss/q-bio.GN | 6 |
| arXiv q-bio.QM | rss.arxiv.org/rss/q-bio.QM | 6 |
| PubMed | eutils.ncbi.nlm.nih.gov/entrez/eutils（machine learning/deep learning） | 6 |
| bioRxiv | api.biorxiv.org/details/biorxiv/{7天前}/{今天} | 6 |

> 注：arXiv 用 rss.arxiv.org 而非 export.arxiv.org（后者在国内易被墙）

## 各日报 cron 模式一览

| 日报 | 时间 | 模式 | fallback | 原因 |
|------|------|------|----------|------|
| 综合新闻 | 08:00 | no_agent + comprehensive.sh | 无（Shell 稳定） | 中文数据源，无需翻译 |
| 科技AI | 12:00 | agent（no_agent=false） | 12:15 tech-ai-fallback.sh | 需英文→中文翻译 |
| 学术 | 18:00 | agent（no_agent=false） | 18:15 academic-fallback.sh | 需英文→中文翻译 |

## 失败处理

| 场景 | 处理方式 |
|------|----------|
| fetch_worker 单源失败 | 该源 `status: "fail"`，显示"暂不可用"，不影响其他源 |
| fetch_worker 全部失败 | 退出码 2，LLM 输出"数据采集服务异常" |
| LLM 翻译失败/超时 | Hermes cron 重试；仍失败则 15 分钟后 fallback cron 英文兜底 |
| 缓存读写异常 | 降级为无缓存模式，记录 WARN 日志 |
| RSSHub 批量故障 | 重试 2 次；config.sh 预留 `RSSHUB_FALLBACK_URL`（下期实现切换） |
| GitHub API 限流 | 配置 `GITHUB_TOKEN` 提升至 5000 次/小时 |

## 手动触发日报

```bash
# 综合新闻（no-agent，直接执行推送）
bash ~/.hermes/scripts/daily-news/scripts/comprehensive.sh

# tech-ai/academic 手动测试（输出英文 Markdown 到 stdout，不推送）
bash ~/.hermes/scripts/daily-news/scripts/tech-ai.sh
bash ~/.hermes/scripts/daily-news/scripts/academic.sh

# agent 模式手动触发（通过 cron）
hermes cron run <job-id>

# 仅抓取数据查看 JSON
python3 ~/.hermes/scripts/daily-news/lib/fetch_worker.py --type tech-ai | python3 -m json.tool

# 健康检查
python3 ~/.hermes/scripts/daily-news/lib/fetch_worker.py --health
```

## 查看日报任务状态

```bash
hermes cron list | grep daily-news
```

## 修改推送时间

```bash
hermes cron list                    # 查看 job-id
hermes cron edit <job-id> --schedule "30 7 * * *"   # 示例：改到 07:30
```

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 整日报推送为空 | fetch_worker 崩溃 | `python3 lib/fetch_worker.py --type X` 调试 |
| 某源显示"暂不可用" | 网络抖动/源宕机 | 查看日志，等待下次执行 |
| agent 日报未推送 | LLM 翻译/推送失败 | 检查 `/tmp/news-{type}-{date}.done` 是否存在；确认 fallback cron 是否触发 |
| 推送延迟超 5 分钟 | 脚本执行 + 队列等待 | 检查 `hermes cron list` 的 last_run_at |
| 任务被禁用 | `enabled: false` | `hermes cron resume <id>` |

## Pitfalls

- **fetch_worker 自行加载配置**：agent 模式下 LLM 直接执行 `python3 lib/fetch_worker.py`，fetch_worker 内部通过 subprocess 调用 `bash -c 'set -a && source config.sh && env -0'` 加载配置，**无需 LLM 额外 source config.sh**
- **`.done` 标记文件**：agent 推送成功后必须 `touch /tmp/news-{type}-{date}.done`，否则 fallback cron 会误判为"未推送"并重复推送英文兜底
- **日期由 LLM 动态获取**：prompt 中让 LLM 执行 `date +%Y-%m-%d` 获取当天日期，不依赖 Hermes cron 的 shell 展开能力
- **arXiv 缓存跨日报复用**：arXiv cs.AI 同时出现在 tech-ai(12:00)和 academic(18:00)，缓存 TTL 设为 8h（非 6h）避免间隔竞态，第二次抓取直接命中缓存
- **从 no-agent 切到 agent 模式时，必须同时清除 script 字段**：`cronjob update --no_agent=false --script=""`，否则 cron 仍以脚本模式运行，prompt 不会被使用
- **已切换到 agent 模式的 cron 不要改回 no-agent**：agent 模式的 prompt 包含翻译指令，改回 no-agent 后会丢失翻译能力
- **No-agent 模式绕过 LLM 翻译指令**：no_agent=true + script 的 cron 任务不加载任何 skill，不经过 LLM。英文源在 no-agent 模式下永远保持英文
- **`hermes send` 不是管道命令**：不能 `script.sh | hermes send`，应通过 `-f` 指定文件
- **Skill 文档 ≠ 实际 cron 命名**：技能描述中的 job 命名可能过期，务必以 `hermes cron list` 的实际注册为准

## 输出格式参考

详见 [format_markdown.py](file:///workspace/lib/format_markdown.py) 中的 `_SOURCE_META` 和 `_TYPE_META` 映射。标准结构：

- 标题：📰/📡/🧬 智讯·XX日报 — 日期
- 分节：## emoji 中文名（每源一节）
- 列表：编号 + **标题** + 摘要 + 🔗 链接
- 结尾：今日趋势点评/归纳（基于数据归纳）+ 执行时间
- 每源 emoji：arXiv 📊 / GitHub 💻 / HN 🔥 / Product Hunt 🚀 / Reddit 💬 / 知乎 🇨🇳 / 36氪 💼 / 微博 🔥 / 百度 🔍 / PubMed 🧬 / bioRxiv 🧬

## 何时调用此 Skill

当用户表达以下意图时自动激活：
- "生成今日新闻日报"
- "推送学术日报"
- "查看今天的 AI 资讯"
- "现在跑一下日报"
- "今日日报怎么样"

也可作为每日定时任务的执行体（已在 cron 中配置）。
