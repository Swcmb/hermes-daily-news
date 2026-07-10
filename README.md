# 智讯日报 — Hermes Daily News System v2.0

运行在 Hermes Agent cron 调度之上的每日新闻推送系统，采用 Shell + Python 混合架构，并行抓取 16 个数据源并推送到 QQ Bot。

## 日报一览

| 类型 | 时间 | 模式 | 数据源数 | 翻译方式 |
|------|------|------|----------|----------|
| 📰 综合新闻 | 08:00 | no-agent（纯 Shell） | 5 | 无需（中文源） |
| 📡 AI 科技 | 12:00 | agent（LLM 翻译） | 6 | LLM 英译中 |
| 🧬 学术前沿 | 18:00 | agent（LLM 翻译） | 7 | LLM 英译中 |

## 目录结构

```
hermes-daily-news/
├── scripts/
│   ├── comprehensive.sh          # 综合新闻（no-agent 完整链路：抓取+格式化+推送）
│   ├── tech-ai.sh                # tech-ai 手动测试入口（抓取+英文格式化到 stdout）
│   ├── tech-ai-fallback.sh       # tech-ai LLM 失败兜底（.done 标记检测→英文推送）
│   ├── academic.sh               # academic 手动测试入口
│   └── academic-fallback.sh      # academic LLM 失败兜底
├── lib/
│   ├── common.sh                 # Shell 公共库（配置加载/日志/Markdown 格式化/推送）
│   ├── fetch_worker.py           # 并行抓取入口（多源并发+超时+重试+缓存+去重）
│   ├── format_markdown.py        # JSON → 中文 Markdown 转换器
│   ├── cache.py                  # 跨脚本文件缓存（TTL + 原子写入）
│   ├── dedup.py                  # 去重（URL 精确 + 标题 hash）
│   └── parsers/
│       ├── __init__.py           # sanitize/sanitize_url/SOURCE_PRIORITY 公共函数
│       ├── rss_parser.py         # RSS/Atom 通用解析（知乎/36氪/牛客/微博/百度）
│       ├── arxiv_parser.py       # arXiv RSS 专用（CDATA/abstract 清洗）
│       ├── github_parser.py      # GitHub Search API JSON
│       ├── hn_parser.py          # Hacker News Algolia API
│       ├── producthunt_parser.py # Product Hunt RSS
│       ├── reddit_parser.py      # Reddit JSON
│       └── pubmed_parser.py      # PubMed E-utilities + bioRxiv API
├── config/
│   └── config.sh                 # 全部可配项（数据源 URL/条数/超时/TTL/推送目标）
├── tests/                        # pytest 单元测试（93 个测试用例）
├── skill/
│   └── SKILL.md                  # Hermes Agent 技能定义（daily-news-editor）
├── deploy.sh                     # 部署脚本（备份+拷贝+渲染 prompt+输出 cron 命令）
└── README.md
```

## 架构设计

### 数据流（no-agent 模式 — comprehensive）

```
comprehensive.sh (source config.sh + common.sh)
    │
    ▼
python3 lib/fetch_worker.py --type comprehensive
    │  ThreadPoolExecutor(max_workers=4) 并行抓取 5 个中文源
    │  每源：缓存检查 → HTTP(超时12s) → 重试(2次指数退避) → 解析
    │  去重：URL 精确 + 标题 hash
    ▼
统一 JSON 数组 → format_markdown.py 生成中文 Markdown
    │
    ▼
send_to_qq → hermes send 推送到 QQ Bot
```

### 数据流（agent 模式 — tech-ai / academic）

```
Hermes cron (no_agent=false + prompt + skill) 启动 LLM agent
    │
    ▼
LLM 执行：python3 lib/fetch_worker.py --type tech-ai
    │  (并行抓取英文源 + 缓存 + 去重)
    ▼
fetch_worker 输出 JSON → LLM 读取
    │
    ▼
LLM 翻译英文标题/摘要为中文，按 SKILL.md 格式生成 Markdown
    │
    ▼
LLM 调用 hermes send 推送中文 Markdown 到 QQ Bot
    │
    └─ 兜底：若 LLM 失败，15 分钟后 fallback cron 检查 .done 标记
       未推送则用英文兜底
```

**关键区别**：no-agent 模式由 Shell 全权负责；agent 模式由 LLM 负责（翻译+格式化+推送），Shell 不参与执行链路。

## 数据源

| 源名 | URL | 类型 | 用于日报 | 条数 |
|------|-----|------|----------|------|
| zhihu | zhihu.com/rss | RSS | comprehensive | 10 |
| 36kr | rsshub.rssforever.com/36kr/newsflashes | RSS | comprehensive | 10 |
| nowcoder | rsshub.rssforever.com/nowcoder/recommend | RSS | comprehensive | 8 |
| weibo | rsshub.rssforever.com/weibo/search/hot | RSS | comprehensive | 10 |
| baidu | rsshub.rssforever.com/baidu/topwords | RSS | comprehensive | 10 |
| arxiv_cs_ai | rss.arxiv.org/rss/cs.AI | arXiv | tech-ai, academic | 6 |
| arxiv_cs_lg | rss.arxiv.org/rss/cs.LG | arXiv | tech-ai, academic | 6 |
| github_ai | api.github.com/search/repositories | GitHub | tech-ai | 8 |
| hn | hn.algolia.com/api/v1/search | JSON | tech-ai | 10 |
| producthunt | producthunt.com/feed | RSS | tech-ai | 6 |
| reddit_ml | reddit.com/r/MachineLearning/top.json | JSON | tech-ai | 6 |
| arxiv_stat_ml | rss.arxiv.org/rss/stat.ML | arXiv | academic | 6 |
| arxiv_qbio_gn | rss.arxiv.org/rss/q-bio.GN | arXiv | academic | 6 |
| arxiv_qbio_qm | rss.arxiv.org/rss/q-bio.QM | arXiv | academic | 6 |
| pubmed | eutils.ncbi.nlm.nih.gov/entrez/eutils | XML | academic | 6 |
| biorxiv | api.biorxiv.org/details/biorxiv/{start}/{end} | JSON | academic | 6 |

## 配置

所有可调项集中在 [config/config.sh](file:///workspace/config/config.sh)，关键配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `COMPREHENSIVE_SOURCES` | zhihu,36kr,nowcoder,weibo,baidu | 综合新闻源列表 |
| `TECH_AI_SOURCES` | arxiv_cs_ai,arxiv_cs_lg,github_ai,hn,producthunt,reddit_ml | AI 科技源列表 |
| `ACADEMIC_SOURCES` | arxiv_cs_ai,arxiv_cs_lg,arxiv_stat_ml,pubmed,biorxiv,arxiv_qbio_gn,arxiv_qbio_qm | 学术源列表 |
| `TIMEOUT_HTTP` | 12 | 单源 HTTP 超时（秒） |
| `MAX_WORKERS` | 4 | 并行抓取线程数 |
| `CACHE_TTL_RSS` | 1800 | RSS 缓存 TTL（30 分钟） |
| `CACHE_TTL_ARXIV` | 28800 | arXiv 缓存 TTL（8 小时，跨 tech-ai/academic 复用） |
| `CACHE_TTL_API` | 600 | API 类源缓存 TTL（10 分钟） |
| `QQ_TARGET` | qqbot:AC6557CF... | QQ Bot 推送目标 |
| `GITHUB_TOKEN` | （空） | 可选，填入提升 API 限流至 5000 次/小时 |

修改配置后无需改代码，下次 cron 执行自动生效。

## 部署

### 自动部署（推荐）

```bash
# 1. 可选：运行 pytest 验证
bash deploy.sh --run-tests

# 2. 部署到默认目录 ~/.hermes/scripts/daily-news/
bash deploy.sh

# 3. 按输出的 cron 命令更新调度任务（需手动确认）
```

`deploy.sh` 自动执行：
1. 备份旧脚本到 `daily-news.bak.{YYYYMMDDHHmmss}/`
2. 拷贝新文件到 `~/.hermes/scripts/daily-news/`
3. 从 config.sh 读取 `QQ_TARGET`，渲染 agent prompt 模板
4. 输出 cron 更新命令（不自动执行）
5. 将渲染后的 prompt 写入 `/tmp/news-prompts-{date}.txt` 供复制

### 手动部署

```bash
# 拷贝文件
cp -r scripts lib config skill ~/.hermes/scripts/daily-news/

# 更新 cron（综合新闻 no-agent）
hermes cron update <id> --script daily-news/scripts/comprehensive.sh --no_agent=true

# 更新 cron（tech-ai agent 模式，需粘贴 prompt）
hermes cron update <id> --no_agent=false --script='' --prompt '<见 /tmp/news-prompts-*.txt>' --skill daily-news-editor

# 可选：创建 fallback cron
hermes cron create --name daily-tech-ai-fallback --schedule "15 12 * * *" --script daily-news/scripts/tech-ai-fallback.sh --no_agent=true
```

**注意**：从 no-agent 切到 agent 模式时，必须同时清除 `--script` 字段（设为空），否则 cron 仍以脚本模式运行。

## 可观测性

### 日志

- 路径：`~/.hermes/logs/news-{type}-{date}.log`
- 格式：`{ISO时间戳} {级别} {日报类型} {源} {状态} {耗时}ms {条数}items {错误信息}`

### 健康检查

```bash
python3 lib/fetch_worker.py --health
```

输出各源可达性状态表（源名 / HTTP 状态 / 耗时 / 是否可达）。

### 单元测试

```bash
cd tests && python3 -m pytest -v
```

共 93 个测试用例，覆盖 7 个 parser + cache + dedup。

## 性能指标

| 日报 | 现状 | 目标 | 缓存命中时 |
|------|------|------|-----------|
| comprehensive | ~50s | <30s | <10s |
| tech-ai | ~120s | <60s | <15s |
| academic | ~150s | <90s | <20s |

优化手段：并行抓取（4 线程）+ 跨脚本缓存复用（arXiv 8h TTL）+ 指数退避重试。

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 整日报推送为空 | fetch_worker 崩溃或 stdout 为空 | `python3 lib/fetch_worker.py --type X` 调试 |
| 某源显示"暂不可用" | 网络抖动/源宕机 | 查看日志，等待下次执行 |
| agent 日报未推送 | LLM 翻译/推送失败 | 检查 `.done` 标记，确认 fallback cron 是否触发 |
| RSSHub 源批量失败 | rsshub.rssforever.com 故障 | config.sh 预留 `RSSHUB_FALLBACK_URL`（下期实现切换） |
| GitHub API 403 | 限流（60 次/小时） | 配置 `GITHUB_TOKEN` 提升至 5000 次/小时 |
| 推送延迟超 5 分钟 | 脚本执行 + 队列等待 | 检查 `hermes cron list` 的 last_run_at |

## 回滚

```bash
# 旧脚本备份在 daily-news.bak.{timestamp}/
rm -rf ~/.hermes/scripts/daily-news
mv ~/.hermes/scripts/daily-news.bak.{timestamp} ~/.hermes/scripts/daily-news

# cron 任务回滚：用旧 script 路径重新 update
hermes cron update <id> --script daily-news/comprehensive-news-daily.sh --no_agent=true
```

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.10 | 使用 `dict | None` 联合类型语法 |
| bash | >= 4.0 | 使用 `source` 命令 |
| Hermes Agent | 当前版本 | cron 调度 + `hermes send` |
| pytest | >= 7.0 | 开发期依赖（非运行时） |

运行时仅依赖 Python 标准库（urllib/json/re/xml/concurrent.futures/hashlib），不引入第三方依赖。

## 许可

CC BY-NC 4.0 — 署名-非商业使用
