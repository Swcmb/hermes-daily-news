# 智讯日报系统重构与拓展设计

- **文档日期**:2026-07-10
- **项目**:hermes-daily-news(Hermes Agent 每日新闻推送系统)
- **状态**:待审核

---

## 1. 背景与现状

智讯日报是运行在 Hermes Agent cron 调度之上的每日新闻推送系统,包含三个 Shell 脚本,分别在 08:00 / 12:00 / 18:00 推送综合新闻、AI 科技、学术前沿日报到 QQ Bot。

### 1.1 现有文件

| 脚本 | 行数 | 模式 | 数据源 |
|------|------|------|--------|
| `comprehensive-news-daily.sh` | 110 | no-agent | 知乎 · 36氪 · 牛客 · GitHub |
| `tech-ai-daily.sh` | 158 | agent | arXiv cs.AI/cs.LG · GitHub · 36氪 |
| `academic-daily.sh` | 157 | agent | arXiv cs.AI/stat.ML/q-bio.GN/q-bio.QM |

### 1.2 现有问题

| 编号 | 问题 | 影响 |
|------|------|------|
| P1 | `fetch()` / `parse_arxiv()` 在三个脚本中重复定义 | 维护成本高,改一处需改三处 |
| P2 | 串行抓取,每源 8-30s 顺序等待 | 综合新闻 50s、学术 150s,体验差 |
| P3 | arXiv cs.AI 被 tech-ai 和 academic 重复抓取 | 浪费带宽与时间 |
| P4 | URL/条数/超时全部硬编码在脚本内 | 调整需改代码,非运维人员难操作 |
| P5 | 无结构化日志,失败原因难追溯 | 故障排查困难 |
| P6 | 无去重,同一论文可能在不同源重复出现 | 内容冗余 |
| P7 | 无单元测试 | 解析逻辑改动无保障 |
| P8 | 数据源单一,无备份源 | 单源宕机即缺数据 |
| P9 | no-agent 脚本中 arXiv 内容仍为英文 | 与"中文优先"原则冲突 |

### 1.3 本次目标

- **代码重构**:抽取公共库,消除三脚本间重复代码
- **性能优化**:并行抓取 + 跨脚本缓存复用,把执行时间压到 30-90s
- **功能拓展**:新增 Hacker News / 微博热搜 / 百度热搜 / PubMed / bioRxiv / Product Hunt / Reddit 七个数据源
- **配置化**:数据源/条数/超时/路径全部可配
- **可观测性**:结构化日志 + pytest 单元测试 + 健康检查

### 1.4 非目标

- 不引入运行时第三方依赖(运行时仅用 Python 标准库;测试用 pytest 例外,属开发期依赖)
- 不替换 Hermes Agent 的 cron 调度机制
- 不构建 Web UI 或 Dashboard
- 不实现历史数据持久化存储(仅缓存当天的抓取结果)
- 不做 LLM 翻译 API 集成(翻译仍由 agent 模式的 LLM 完成)

---

## 2. 总体架构

### 2.1 目录结构

```
hermes-daily-news/
├── scripts/
│   ├── comprehensive.sh          # 综合新闻(no-agent, 中文源, 完整链路:抓取+格式化+推送)
│   ├── tech-ai.sh                # tech-ai 手动测试入口(抓取+英文格式化,输出到 stdout,不推送)
│   ├── tech-ai-fallback.sh       # tech-ai LLM 失败兜底(检查 .done 标记→调用 tech-ai.sh 逻辑→推送)
│   ├── academic.sh               # academic 手动测试入口(抓取+英文格式化,输出到 stdout,不推送)
│   └── academic-fallback.sh      # academic LLM 失败兜底(检查 .done 标记→调用 academic.sh 逻辑→推送)
├── lib/
│   ├── common.sh                 # Shell 公共:配置加载/日志/Markdown格式化
│   ├── fetch_worker.py           # 并行抓取入口(多源并发+超时+重试+缓存)
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── rss_parser.py         # RSS/Atom 通用解析(知乎/36氪/牛客/微博/百度)
│   │   ├── arxiv_parser.py       # arXiv RSS 专用(CDATA/abstract 清洗)
│   │   ├── github_parser.py      # GitHub Search API JSON
│   │   ├── hn_parser.py          # Hacker News Algolia API JSON
│   │   ├── producthunt_parser.py # Product Hunt RSS
│   │   ├── reddit_parser.py      # Reddit JSON
│   │   └── pubmed_parser.py      # PubMed E-utilities + bioRxiv API
│   ├── cache.py                  # 跨脚本文件缓存(TTL)
│   └── dedup.py                  # 去重(URL精确 + 标题hash)
├── config/
│   └── config.sh                 # 全部可配项(数据源/条数/超时/路径)
├── tests/
│   ├── test_arxiv_parser.py
│   ├── test_rss_parser.py
│   ├── test_github_parser.py
│   ├── test_hn_parser.py
│   ├── test_producthunt_parser.py
│   ├── test_reddit_parser.py
│   ├── test_pubmed_parser.py
│   ├── test_dedup.py
│   ├── test_cache.py
│   └── fixtures/                 # 真实 RSS/JSON 样本(脱敏)
├── skill/
│   └── SKILL.md
├── deploy.sh                     # 部署脚本(拷贝+输出cron更新命令)
└── README.md
```

### 2.2 数据流

**no-agent 模式(comprehensive)**:

```
Shell 入口(source config.sh + lib/common.sh)
        │
        ▼
python3 lib/fetch_worker.py --type comprehensive
        │  ThreadPoolExecutor(max_workers=4) 并行抓取所有源
        │  每源:缓存命中检查 → HTTP(超时12s) → 重试(2次指数退避) → 解析
        │  跨脚本缓存:arXiv cs.AI 当天 tech-ai 与 academic 复用
        │  去重:URL精确 + 标题normalize后hash
        ▼
统一 JSON 数组输出到 stdout
        │
        ▼
Shell 格式化函数(common.sh)读取 JSON → 生成中文 Markdown
        │
        ▼
common.sh 的 send_to_qq 函数调用 hermes send 推送到 QQ Bot
```

**agent 模式(tech-ai / academic)**:

```
Hermes cron 以 no_agent=false + prompt + skill 启动 LLM agent
        │
        ▼
LLM 按 prompt 指示,执行 shell 命令:
    python3 lib/fetch_worker.py --type tech-ai
        │  (同上:并行抓取 + 缓存 + 去重)
        ▼
fetch_worker 输出 JSON 到 stdout,LLM 直接读取
        │
        ▼
LLM 将英文标题/摘要翻译为中文,按 SKILL.md 格式生成中文 Markdown
        │
        ▼
LLM 调用 hermes send 推送中文 Markdown 到 QQ Bot
        │
        └─ 异步兜底:若 LLM 翻译失败/超时,延迟 15 分钟后由独立的 fallback cron
           (见 8.2 节)检查 .done 标记,未推送则用英文 JSON 生成简易 Markdown 推送
```

**关键区别**:no-agent 模式由 Shell 脚本全权负责(抓取+格式化+推送);agent 模式由 LLM 负责(抓取命令+翻译+格式化+推送),Shell 不参与 agent 模式的执行链路。

### 2.3 统一数据结构

所有源解析为统一 JSON 结构,便于 Shell 格式化与 LLM 翻译:

```json
[
  {
    "source": "arxiv_cs_ai",
    "source_type": "arxiv",
    "fetched_at": "2026-07-10T12:00:00+08:00",
    "status": "ok",
    "item_count": 6,
    "cache_hit": false,
    "elapsed_ms": 3200,
    "items": [
      {
        "title": "Paper Title Here",
        "url": "https://arxiv.org/abs/2026.12345",
        "abstract": "First 200 chars of abstract...",
        "meta": {
          "arxiv_id": "2026.12345",
          "lang": "en"
        }
      }
    ]
  },
  {
    "source": "zhihu",
    "source_type": "rss",
    "fetched_at": "2026-07-10T08:00:00+08:00",
    "status": "fail",
    "error": "HTTP 503 after 2 retries",
    "items": []
  }
]
```

`status` 枚举:`ok` / `fail` / `cache_hit` / `empty`。

---

## 3. 模块设计

### 3.1 lib/common.sh(Shell 公共函数)

| 函数 | 职责 | 签名 |
|------|------|------|
| `load_config` | source config.sh 并导出变量 | `load_config` |
| `log_info` / `log_warn` / `log_error` | 结构化日志写入文件 | `log_info "message"` |
| `format_header` | 日报标题头 | `format_header "📰" "综合新闻" "$DATE" "$TIMESTAMP"` |
| `format_section` | 分节标题 | `format_section "🇨🇳" "国内热点" "知乎热榜 Top 10"` |
| `format_listitem` | 编号列表项 | `format_listitem 1 "**标题**" "描述"` |
| `format_footer` | 结尾(执行时间/提示) | `format_footer "$SCRIPT_TIMEOUT" "$TIMESTAMP"` |
| `send_to_qq` | 推送 Markdown 到 QQ Bot | `send_to_qq "$QQ_TARGET" "$MARKDOWN_FILE"` |
| `cleanup` | trap EXIT 时清理临时文件 | `cleanup` |

**send_to_qq 实现说明**:
```bash
send_to_qq() {
    local target="$1"      # QQ bot ID,如 qqbot:AC6557CF43ED1A86EA5C1A17C72B5B6D
    local md_file="$2"     # Markdown 文件路径
    hermes send -f "$md_file" -t "$target"
}
```
`QQ_TARGET` 在 config.sh 中配置。

日志格式:
```
2026-07-10T08:00:12+08:00 INFO  comprehensive zhihu ok 3200ms 10items
2026-07-10T08:00:15+08:00 WARN  comprehensive 36kr fail "HTTP 503 after 2 retries"
```

### 3.2 lib/fetch_worker.py(并行抓取入口)

**职责**:接收 `--type` 参数,读取配置,并行抓取所有源,输出统一 JSON 到 stdout。

**CLI 接口**:
```
python3 lib/fetch_worker.py --type comprehensive [--sources zhihu,36kr] [--no-cache] [--health]
```

| 参数 | 说明 |
|------|------|
| `--type` | 日报类型:`comprehensive` / `tech-ai` / `academic` |
| `--sources` | 可选,覆盖配置中的源列表(逗号分隔) |
| `--no-cache` | 跳过缓存,强制重新抓取 |
| `--health` | 健康检查模式,只测可达性不输出 JSON |

**退出码**:
- `0`:全部源成功(含缓存命中)
- `1`:部分源失败
- `2`:全部源失败

**核心逻辑**:
```python
def main():
    args = parse_args()
    config = load_config()                   # 内部自行 source config.sh(见下)
    sources = resolve_sources(args, config)  # 解析要抓取的源列表
    results = fetch_all(sources, config)     # ThreadPoolExecutor 并行
    results = dedup_results(results)         # 去重
    print(json.dumps(results, ensure_ascii=False))
```

**配置加载机制**(关键:fetch_worker 自行加载,不依赖外部 shell):
```python
def load_config() -> dict:
    """基于 __file__ 定位项目根,内部 source config.sh 并解析环境变量"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_sh = os.path.join(project_root, 'config', 'config.sh')
    # 通过 subprocess 调用 bash source 并导出所有变量
    result = subprocess.run(
        ['bash', '-c', f'source "{config_sh}" && env -0'],
        capture_output=True, text=True
    )
    config = {}
    for entry in result.stdout.split('\0'):
        if '=' in entry:
            key, _, val = entry.partition('=')
            config[key] = val
    return config
```
这样无论 agent 模式(LLM 直接执行 python3)还是 no-agent 模式(Shell 调用 python3),fetch_worker 都能自行加载配置,**不依赖外部 shell 预先 source config.sh**。

**性能要点**:
- `ThreadPoolExecutor(max_workers=4)`:I/O 密集型,4 线程足够且避免限流
- 每源独立 `try/except`,失败不阻断其他源
- 缓存命中时跳过 HTTP,直接返回缓存内容
- `json.dumps` 一次性输出,不累积大列表

### 3.3 lib/parsers/(解析器)

每个 parser 为纯函数模块,仅暴露 `parse(raw_content: str, limit: int) -> list[dict]`,无副作用,便于 pytest。

**内容安全**:所有 parser 在解析后统一执行 `sanitize(text)` 清洗:
- 剥离 HTML 标签(`<script>` / `<img>` / `<a>` 等,正则 `<[^>]+>`)
- 转义 Markdown 特殊字符(`[` / `]` / `(` / `)` 在标题中转义,避免破坏格式)
- 校验 URL 协议为 `http` / `https`(拒绝 `javascript:` / `file:` 等)
- 截断超长字段(title > 200 字符、abstract > 300 字符)

| 模块 | 输入 | 输出 | 关键逻辑 |
|------|------|------|----------|
| `rss_parser.py` | RSS/Atom XML | `list[dict]` | 正则提取 `<item>` 块,解析 title/link/description,HTML 实体反转义 + sanitize |
| `arxiv_parser.py` | arXiv RSS XML | `list[dict]` | CDATA 解包,abstract 清洗(去 `arXiv:xxx Announce Type` 前缀),提取 arxiv_id + sanitize |
| `github_parser.py` | GitHub Search API JSON | `list[dict]` | 解析 items,提取 full_name/description/stargazers_count/language + sanitize |
| `hn_parser.py` | Algolia API JSON | `list[dict]` | 解析 hits,提取 title/url/points/num_comments + sanitize |
| `producthunt_parser.py` | Product Hunt RSS XML | `list[dict]` | 复用 rss_parser,补充 votes 提取 |
| `reddit_parser.py` | Reddit JSON | `list[dict]` | 解析 data.children,提取 title/url_permalink/score + sanitize |
| `pubmed_parser.py` | PubMed XML + bioRxiv JSON | `list[dict]` | PubMed E-utilities esearch + esummary 串行两步(esummary URL 根据 esearch 结果动态拼接);bioRxiv details API + sanitize |

### 3.4 lib/cache.py(文件缓存)

**职责**:跨脚本共享的文件缓存,避免同一天内重复抓取。

**缓存策略**:
- 缓存目录:`/tmp/hermes-news-cache/`(可配)
- 缓存 key:`sha1(占位符替换后的最终URL).json`(确保不同日期的 GitHub/bioRxiv 请求不共享缓存)
- 缓存内容:解析后的 JSON(items 列表)+ 元数据(fetched_at)
- TTL 按源类型区分:

| 源类型 | TTL | 理由 |
|--------|-----|------|
| RSS(知乎/36氪/微博等) | 30 min | 新闻更新快 |
| arXiv | 8 h | 论文一天更新一次;设 8h 而非 6h,留余量避免 tech-ai(12:00)与 academic(18:00)间隔 6h 的整点竞态 |
| GitHub | 1 h | 趋势变化较快 |
| API(HN/Reddit/PubMed) | 10 min | 社区热点更新快 |

**原子写入**:先写 `.tmp` 临时文件,再 `os.rename` 原子替换,避免并发损坏。

**清理机制**:`fetch_worker.py` 每次启动时调用两个清理函数:
- `clear_expired(cache_dir)`:清理缓存目录内 TTL 过期的缓存文件
- `clear_done_markers(retention_hours)`:清理 `/tmp/news-*.done` 标记文件(供 fallback 机制用,见 8.2 节),避免历史标记干扰次日判断

`config.sh` 可配 `CACHE_RETENTION_HOURS=48`(默认 48 小时,超过即清理)。

**接口**:
```python
def get_cache(url: str, ttl: int) -> dict | None
def set_cache(url: str, data: dict) -> None
def clear_expired(cache_dir: str, retention_hours: int = 48) -> int  # 清理缓存文件,返回清理数量
def clear_done_markers(retention_hours: int = 48) -> int  # 清理 /tmp/news-*.done 标记,返回清理数量
```

### 3.5 lib/dedup.py(去重)

**职责**:单次运行内跨源去重,避免同一条目在不同源重复出现(注:跨运行的去重不在范围内,arXiv cs.AI 会同时出现在 tech-ai 和 academic 两份日报中,这是设计决策——两份日报面向不同读者群)。

**输入输出契约**:
- 输入:fetch_worker 的源级别结果数组(结构见 2.3 节,每个元素含 `source` / `items` 字段)
- 输出:同结构数组,去重后的 items 从后续源中移除,保留首次出现的源;被移除条目所在源的 `item_count` 同步更新

**策略**(O(n),极低消耗):
1. **URL 精确匹配**:归一化 URL(去 query string 中跟踪参数 `utm_*` / `fbclid` / `gclid` / `ref` / `source`)后放入集合,命中则丢弃
2. **标题 hash**:标题 `lowercase` → 去标点(正则 `[^\w\u4e00-\u9fff]`,保留中英文字符与数字)→ 分词排序 → `sha1` 前 16 字节,命中则丢弃

**源优先级**(保留首次出现,按 fetch_worker 返回顺序):
```
arxiv_cs_ai > arxiv_cs_lg > arxiv_stat_ml > arxiv_qbio_gn > arxiv_qbio_qm
> pubmed > biorxiv > github_ai > hn > reddit_ml > producthunt
> zhihu > 36kr > nowcoder > weibo > baidu
```
即:论文源优先于社区源,学术源优先于综合源。fetch_worker 按此顺序返回结果,dedup 保留靠前源的条目。

不使用 NLP 相似度计算(消耗大),标题 hash 已覆盖 90%+ 重复场景。

**接口**:
```python
def dedup(results: list[dict]) -> list[dict]
    # 输入源级别数组,输出去重后的同结构数组,更新 item_count
```

---

## 4. 数据源拓展

### 4.1 源分配策略(中英分流)

| 日报 | 模式 | 源语言 | 数据源 |
|------|------|--------|--------|
| comprehensive | no-agent | 全中文 | 知乎 · 36氪 · 牛客 · **微博热搜(新)** · **百度热搜(新)** |
| tech-ai | agent | 英文→LLM翻译 | arXiv cs.AI/cs.LG · GitHub · **Hacker News(新)** · **Product Hunt(新)** · **Reddit r/ML(新)** |
| academic | agent | 英文→LLM翻译 | arXiv cs.AI/cs.LG/stat.ML/q-bio.GN/q-bio.QM · **PubMed(新)** · **bioRxiv(新)** |

**原则**:英文源全部归入 agent 模式脚本,由 LLM 翻译;中文源归入 no-agent 脚本,无需翻译。满足"全中文输出"且不引入翻译 API 依赖。

### 4.2 新增数据源详情

| 源 | URL | 格式 | 条数 | 备注 |
|----|-----|------|------|------|
| 微博热搜 | `https://rsshub.rssforever.com/weibo/search/hot` | RSS | 10 | 经 RSSHub |
| 百度热搜 | `https://rsshub.rssforever.com/baidu/topwords` | RSS | 10 | 经 RSSHub |
| Hacker News | `https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=10` | JSON | 10 | Algolia API,无需 token |
| Product Hunt | `https://www.producthunt.com/feed` | RSS | 6 | 官方 feed |
| Reddit r/ML | `https://www.reddit.com/r/MachineLearning/top.json?t=day&limit=10` | JSON | 6 | 需 User-Agent |
| PubMed | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmax=6&sort=date&term=(machine+learning)+OR+(deep+learning)` | XML | 6 | E-utilities 两步:esearch 取 ID 列表 → esummary(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={ids}`)批量取详情,esummary URL 在 parser 内根据 esearch 结果动态拼接 |
| bioRxiv | `https://api.biorxiv.org/details/biorxiv/{start_date}/{end_date}/0/25` | JSON | 6 | 日期区间查询 |

### 4.3 源元数据注册

每个源在 `config.sh` 中注册:URL、条数、超时、TTL、parser 类型。`fetch_worker.py` 根据源名查表获取抓取与解析参数。

---

## 5. 性能优化策略

### 5.1 并行抓取

- `ThreadPoolExecutor(max_workers=4)`,I/O 密集场景线程池足够
- 每源独立超时 12s,不互相阻塞
- 失败源不阻断其他源,降级显示"暂不可用"

### 5.2 缓存复用

- 同一天内,tech-ai(12:00)与 academic(18:00)共享 arXiv cs.AI 缓存
- 缓存命中时跳过 HTTP,直接返回解析结果
- atomic write 避免并发损坏

### 5.3 重试机制

- 每源最多重试 2 次,指数退避(1s → 2s)
- 3 次全失败则标记 `status: "fail"`,降级显示
- 重试只对 5xx / 网络错误生效,4xx 不重试

### 5.4 执行时间目标

| 日报 | 现状 | 目标 | 缓存命中时 |
|------|------|------|-----------|
| comprehensive | ~50s | <30s | <10s |
| tech-ai | ~120s | <60s | <15s |
| academic | ~150s | <90s | <20s |

### 5.5 资源消耗控制

- 仅用 Python 标准库:`urllib` / `json` / `re` / `xml.etree` / `concurrent.futures` / `hashlib`
- 不引入 `requests` / `PyYAML` / `lxml` 等第三方库
- parser 流式解析,fetch 后立即解析释放原始内容
- `json.dumps` 一次性 stdout,不累积大列表在内存
- 线程数固定 4,不随源数增长

---

## 6. 配置化

### 6.1 config/config.sh

Shell 可 source 的配置文件,`fetch_worker.py` 通过环境变量读取。

```bash
# ===== 数据源映射 =====
COMPREHENSIVE_SOURCES="zhihu,36kr,nowcoder,weibo,baidu"
TECH_AI_SOURCES="arxiv_cs_ai,arxiv_cs_lg,github_ai,hn,producthunt,reddit_ml"
ACADEMIC_SOURCES="arxiv_cs_ai,arxiv_cs_lg,arxiv_stat_ml,pubmed,biorxiv,arxiv_qbio_gn,arxiv_qbio_qm"

# ===== 条数限制 =====
ZHIHU_LIMIT=10
KR_LIMIT=10
NOWCODER_LIMIT=8
WEIBO_LIMIT=10
BAIDU_LIMIT=10
ARXIV_LIMIT=6
GITHUB_LIMIT=8
HN_LIMIT=10
PRODUCTHUNT_LIMIT=6
REDDIT_LIMIT=6
PUBMED_LIMIT=6
BIORXIV_LIMIT=6

# ===== 超时 =====
TIMEOUT_HTTP=12
SCRIPT_TIMEOUT_COMPREHENSIVE=30
SCRIPT_TIMEOUT_TECH_AI=60
SCRIPT_TIMEOUT_ACADEMIC=90
RETRY_MAX=2
RETRY_BACKOFF_BASE=1

# ===== 并发 =====
MAX_WORKERS=4

# ===== 缓存 =====
CACHE_DIR="/tmp/hermes-news-cache"
CACHE_TTL_RSS=1800
CACHE_TTL_ARXIV=28800
CACHE_TTL_GITHUB=3600
CACHE_TTL_API=600
CACHE_RETENTION_HOURS=48       # 缓存文件保留时长,超过则清理
RSSHUB_FALLBACK_URL=""         # 备用 RSSHub 实例(本期留空,下期实现故障切换)

# ===== 日志 =====
LOG_DIR="${HOME}/.hermes/logs"
LOG_LEVEL="INFO"
# TIMESTAMP 由 common.sh 在 load_config 后生成,格式 ISO8601(与日志一致):
# TIMESTAMP="$(date +%Y-%m-%dT%H:%M:%S%z)"
# DATE 由 common.sh 生成:DATE="$(date +%Y年%-m月%-d日)"
# 注意:备份目录用 YYYYMMDDHHmmss 格式(见 9.3 节),与 TIMESTAMP(ISO8601)区分用途

# ===== 数据源 URL =====
ZHIHU_URL="https://www.zhihu.com/rss"
KR_URL="https://rsshub.rssforever.com/36kr/newsflashes"
NOWCODER_URL="https://rsshub.rssforever.com/nowcoder/recommend"
WEIBO_URL="https://rsshub.rssforever.com/weibo/search/hot"
BAIDU_URL="https://rsshub.rssforever.com/baidu/topwords"
ARXIV_AI_URL="https://rss.arxiv.org/rss/cs.AI"
ARXIV_LG_URL="https://rss.arxiv.org/rss/cs.LG"
ARXIV_STATML_URL="https://rss.arxiv.org/rss/stat.ML"
ARXIV_QBIO_GN_URL="https://rss.arxiv.org/rss/q-bio.GN"
ARXIV_QBIO_QM_URL="https://rss.arxiv.org/rss/q-bio.QM"
HN_URL="https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=10"
PRODUCTHUNT_URL="https://www.producthunt.com/feed"
REDDIT_ML_URL="https://www.reddit.com/r/MachineLearning/top.json?t=day&limit=10"
PUBMED_URL="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmax=6&sort=date&term=(machine+learning)+OR+(deep+learning)"
BIORXIV_URL="https://api.biorxiv.org/details/biorxiv/{start_date}/{end_date}/0/25"
GITHUB_AI_URL="https://api.github.com/search/repositories?q=created:>{7d_ago}+topic:llm+OR+topic:agent&sort=stars&order=desc&per_page=8"

# ===== 推送目标 =====
QQ_TARGET="qqbot:AC6557CF43ED1A86EA5C1A17C72B5B6D"

# ===== HTTP 头 =====
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) hermes-daily-news/2.0"
GITHUB_TOKEN=""  # 可选,留空则匿名访问(60次/小时);填入 token 提升至 5000次/小时
```

### 6.2 源注册表

`fetch_worker.py` 内置源注册表,映射源名 → (URL 环境变量名, parser 类型, TTL 环境变量名, limit 环境变量名)。**源名必须与 config.sh 中 `*_SOURCES` 列表的名称完全一致**:

```python
SOURCE_REGISTRY = {
    # comprehensive 源(中文)
    "zhihu":         ("ZHIHU_URL",         "rss",       "CACHE_TTL_RSS",    "ZHIHU_LIMIT"),
    "36kr":          ("KR_URL",            "rss",       "CACHE_TTL_RSS",    "KR_LIMIT"),
    "nowcoder":      ("NOWCODER_URL",      "rss",       "CACHE_TTL_RSS",    "NOWCODER_LIMIT"),
    "weibo":         ("WEIBO_URL",         "rss",       "CACHE_TTL_RSS",    "WEIBO_LIMIT"),
    "baidu":         ("BAIDU_URL",         "rss",       "CACHE_TTL_RSS",    "BAIDU_LIMIT"),
    # tech-ai 源(英文)
    "arxiv_cs_ai":   ("ARXIV_AI_URL",      "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "arxiv_cs_lg":   ("ARXIV_LG_URL",      "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "github_ai":     ("GITHUB_AI_URL",     "github",    "CACHE_TTL_GITHUB", "GITHUB_LIMIT"),
    "hn":            ("HN_URL",            "hn",        "CACHE_TTL_API",    "HN_LIMIT"),
    "producthunt":   ("PRODUCTHUNT_URL",   "producthunt","CACHE_TTL_API",   "PRODUCTHUNT_LIMIT"),
    "reddit_ml":     ("REDDIT_ML_URL",     "reddit",    "CACHE_TTL_API",    "REDDIT_LIMIT"),
    # academic 源(英文)
    "arxiv_stat_ml": ("ARXIV_STATML_URL",  "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "arxiv_qbio_gn": ("ARXIV_QBIO_GN_URL", "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "arxiv_qbio_qm": ("ARXIV_QBIO_QM_URL", "arxiv",     "CACHE_TTL_ARXIV",  "ARXIV_LIMIT"),
    "pubmed":        ("PUBMED_URL",        "pubmed",    "CACHE_TTL_API",    "PUBMED_LIMIT"),
    "biorxiv":       ("BIORXIV_URL",       "pubmed",    "CACHE_TTL_API",    "BIORXIV_LIMIT"),
}
```

### 6.3 URL 占位符解析

部分 URL 含动态占位符,由 `fetch_worker.py` 在运行时用 `datetime` 计算替换:

| 占位符 | 替换值 | 涉及源 |
|--------|--------|--------|
| `{7d_ago}` | 今天减 7 天,格式 `YYYY-MM-DD` | github_ai |
| `{start_date}` | 今天减 7 天,格式 `YYYY-MM-DD` | biorxiv |
| `{end_date}` | 今天,格式 `YYYY-MM-DD` | biorxiv |

`fetch_worker.py` 在发起 HTTP 请求前,用正则 `re.sub(r'\{(\w+)\}', replacer, url)` 替换所有占位符。未识别的占位符保持原样并记录 WARN 日志。

---

## 7. 可观测性

### 7.1 日志

- **路径**:`~/.hermes/logs/news-{type}-{date}.log`
- **格式**:`{ISO时间戳} {级别} {日报类型} {源} {状态} {耗时}ms {条数}items {错误信息}`
- **写入**:`common.sh` 的 `log_info` / `log_warn` / `log_error` 函数统一写入
- **级别**:INFO(正常)/ WARN(部分失败)/ ERROR(全部失败)

### 7.2 错误处理

| 场景 | 处理 |
|------|------|
| 单源 HTTP 超时 | 重试 2 次,仍失败则该源 `status: "fail"`,显示"暂不可用" |
| 单源解析异常 | 该源 `status: "fail"`,记录异常信息,不影响其他源 |
| 全部源失败 | fetch_worker 退出码 2,Shell 输出"全部数据源暂不可用"兜底 |
| 缓存读写异常 | 降级为无缓存模式,记录 WARN 日志 |
| JSON 输出异常 | 退出码 2,Shell 输出错误信息 |
| fetch_worker 异常崩溃(非 0/1/2 退出码) | Shell 检查 stdout 是否有有效 JSON;无则输出"数据采集服务异常,请检查日志"并记录 ERROR;exit code 127(命令未找到)提示检查 python3 路径;exit code 137(被信号杀死)提示内存不足 |
| fetch_worker stdout 为空 | Shell 判定 fetch 失败,输出兜底消息,不尝试解析空输入 |

### 7.3 健康检查

```bash
python3 lib/fetch_worker.py --health
```

输出各源可达性状态表(源名 / HTTP 状态 / 耗时 / 是否可达),便于运维巡检。

### 7.4 单元测试

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_arxiv_parser.py` | arXiv RSS 解析(CDATA / abstract 清洗 / arxiv_id 提取 / 截断容忍) |
| `test_rss_parser.py` | 通用 RSS 解析(HTML 实体 / 空内容 / 异常 XML / sanitize) |
| `test_github_parser.py` | GitHub JSON 解析(空 items / 缺字段 / description 含换行) |
| `test_hn_parser.py` | HN Algolia JSON 解析 |
| `test_producthunt_parser.py` | Product Hunt RSS 解析 |
| `test_reddit_parser.py` | Reddit JSON 解析 |
| `test_pubmed_parser.py` | PubMed XML + bioRxiv JSON 解析 |
| `test_dedup.py` | URL 去重 / 标题 hash 去重 / 跨源去重 / item_count 更新 |
| `test_cache.py` | 缓存命中 / 过期失效 / 原子写入 / clear_expired |

**fixtures**:从真实抓取结果中截取脱敏样本,存入 `tests/fixtures/`。

**运行**:`cd tests && python3 -m pytest -v`

---

## 8. 翻译策略

### 8.1 模式分流

| 日报 | 模式 | 翻译方式 | 理由 |
|------|------|----------|------|
| comprehensive | no-agent | 无需翻译(中文源) | 知乎/36氪/牛客/微博/百度均为中文 |
| tech-ai | agent | LLM 翻译 | arXiv/HN/Reddit/ProductHunt 为英文 |
| academic | agent | LLM 翻译 | arXiv/PubMed/bioRxiv 为英文 |

### 8.2 agent 模式工作方式

agent 模式下,LLM 是执行主体,Shell 脚本不参与:

1. Hermes cron 以 `no_agent=false --prompt="..." --skill=daily-news-editor` 启动 LLM agent
2. LLM 按 prompt 指示,在 agent session 中执行 shell 命令 `python3 lib/fetch_worker.py --type tech-ai`
3. `fetch_worker.py` 输出结构化 JSON(英文标题/摘要)到 stdout,LLM 直接读取 stdout
4. LLM 将英文标题与摘要翻译为中文,按 SKILL.md 格式生成中文 Markdown
5. LLM 调用 `hermes send` 推送中文 Markdown 到 QQ Bot

agent prompt 模板(以 tech-ai 为例,创建 cron 时写入,QQ_TARGET 需替换为实际值):

```
你是智讯日报主编。请执行以下步骤生成今日 AI 科技日报:

1. 运行命令:python3 ~/.hermes/scripts/daily-news/lib/fetch_worker.py --type tech-ai
   (fetch_worker 会自行加载 config.sh 配置,无需额外 source)
2. 读取命令输出的 JSON 数据(包含 arXiv/GitHub/HN/ProductHunt/Reddit 各源条目)
3. 将所有英文标题与摘要翻译为简体中文(保留专业术语如 LLM/Agent/GAN 的原文)
4. 按以下格式输出 Markdown 日报:
   - 每个数据源作为一个 ## 分节
   - 每条目:编号 + **中文标题** + 摘要(意译,限 150 字) + 原始链接
   - 结尾附今日洞察(基于数据归纳 3 条趋势)
5. 用今天的日期作为文件名标识:运行 date +%Y-%m-%d 获取当天日期(记为 DATE),
   将 Markdown 写入 /tmp/news-tech-ai-${DATE}.md
6. 执行推送:hermes send -f /tmp/news-tech-ai-${DATE}.md -t qqbot:AC6557CF43ED1A86EA5C1A17C72B5B6D
7. 推送成功后创建标记文件:touch /tmp/news-tech-ai-${DATE}.done

翻译规范:标题必译,摘要意译,专业术语保留英文,人名保留英文。
```

**注意**:
- prompt 中的 QQ 目标 ID(`qqbot:AC6557CF...`)需在创建 cron 时替换为 config.sh 中 `QQ_TARGET` 的实际值
- **日期由 LLM 在执行时动态获取**(步骤 5 运行 `date +%Y-%m-%d`),不依赖 Hermes cron 的 shell 展开能力,确保每日文件名唯一
- 步骤 7 的 `.done` 标记文件供 fallback cron 检测(见 8.2 节 LLM 失败兜底)
- **.done 标记清理**:fetch_worker 启动时 `clear_done_markers` 会清理 `/tmp/news-*.done` 中超过 48 小时的标记文件(独立函数,与 `clear_expired` 分离;复用 `CACHE_RETENTION_HOURS` 作为保留时长),避免历史标记干扰次日 fallback 判断

**LLM 失败兜底**(高级风险缓解,tech-ai 与 academic 对称):

> **定位**:fallback 脚本为**强烈建议项**(agent 模式无 fallback 时,LLM 失败即当日无推送);目录结构中预留脚本骨架,是否启用 fallback cron 由部署时配置决定。

- 若 agent session 超时或 LLM 未能推送,Hermes cron 的失败重试机制触发
- 可选:配置 no-agent 的 fallback cron(延迟 15 分钟),当 agent 日报未推送时用英文兜底
- **触发检测机制**(.done 标记文件):
  - agent 推送成功后创建 `/tmp/news-{type}-{date}.done` 标记文件(见 prompt 步骤 7)
  - fallback 脚本启动时检查该标记文件,若存在则退出(避免重复推送);若不存在则执行英文兜底推送
  - fallback 脚本推送成功后也创建 `.done` 标记
- **tech-ai fallback**:`scripts/tech-ai-fallback.sh` + `daily-tech-ai-fallback` cron(12:15 执行)
- **academic fallback**:`scripts/academic-fallback.sh` + `daily-academic-fallback` cron(18:15 执行)
- fallback 脚本调用同一 fetch_worker.py,跳过翻译,用 common.sh 格式化英文输出(标注"翻译暂不可用,以下为英文原文")

### 8.3 no-agent 模式输出与推送

`comprehensive.sh` 直接输出中文 Markdown(数据源本身为中文),无需 LLM 参与,稳定性最高。

完整链路:
1. `comprehensive.sh` source config.sh + common.sh
2. 调用 `python3 lib/fetch_worker.py --type comprehensive` 获取 JSON
3. common.sh 格式化函数读取 JSON 生成中文 Markdown,写入临时文件 `/tmp/news-comprehensive-{date}.md`
4. 调用 `send_to_qq "$QQ_TARGET" "/tmp/news-comprehensive-{date}.md"` 推送到 QQ Bot
5. trap EXIT 时 cleanup 清理临时文件

---

## 9. 部署与迁移

### 9.1 部署目录

部署到 `~/.hermes/scripts/daily-news/`:
```
~/.hermes/scripts/daily-news/
├── scripts/
├── lib/
├── config/
├── skill/
└── deploy.sh
```

### 9.2 cron 任务更新

先查询现有任务 ID:
```bash
hermes cron list | grep daily-news
```

**脚本名映射**(旧 → 新):
| 旧脚本名 | 新脚本名 |
|----------|----------|
| `comprehensive-news-daily.sh` | `comprehensive.sh` |
| `tech-ai-daily.sh` | `tech-ai.sh`(agent 模式不再用脚本,仅 fallback 用) |
| `academic-daily.sh` | `academic.sh`(agent 模式不再用脚本,仅 fallback 用) |

| 任务名 | 调度 | 模式 | 命令 |
|--------|------|------|------|
| daily-comprehensive-news | `0 8 * * *` | no-agent | `hermes cron update <id> --script daily-news/scripts/comprehensive.sh --no_agent=true` |
| daily-tech-ai | `0 12 * * *` | agent | `hermes cron update <id> --no_agent=false --script="" --prompt "<见8.2节模板>" --skill daily-news-editor` |
| daily-academic | `0 18 * * *` | agent | `hermes cron update <id> --no_agent=false --script="" --prompt "<见8.2节模板,type改为academic>" --skill daily-news-editor` |
| daily-tech-ai-fallback(可选) | `15 12 * * *` | no-agent | `hermes cron create --name daily-tech-ai-fallback --schedule "15 12 * * *" --script daily-news/scripts/tech-ai-fallback.sh --no_agent=true` |
| daily-academic-fallback(可选) | `15 18 * * *` | no-agent | `hermes cron create --name daily-academic-fallback --schedule "15 18 * * *" --script daily-news/scripts/academic-fallback.sh --no_agent=true` |

**注意**:从 no-agent 切到 agent 模式时,必须同时清除 `--script` 字段(设为空),否则 cron 仍以脚本模式运行。

### 9.3 deploy.sh 脚本

```bash
# deploy.sh 自动执行:
# 1. 备份旧脚本到 ~/.hermes/scripts/daily-news.bak.{YYYYMMDDHHmmss}/
# 2. 拷贝新文件到 ~/.hermes/scripts/daily-news/
# 3. 从 config.sh 读取 QQ_TARGET,渲染 8.2 节 prompt 模板(替换 QQ 目标 ID 为实际值)
# 4. 输出 cron 更新命令(含渲染后的完整 prompt,不自动执行,需用户确认)
# 5. 运行 pytest 验证(可选)
```

**命名规范**:
- 备份目录 `{timestamp}` 格式:`YYYYMMDDHHmmss`(如 `20260710080000`),文件名友好无特殊字符
- 日报临时文件 `{date}` 格式:`YYYY-MM-DD`(如 `2026-07-10`)
- 路径规范:agent 模式 prompt 中必须用绝对路径(因 LLM 工作目录不确定);no-agent 脚本中用相对路径(脚本已 cd 到项目根)

### 9.4 回滚

- 旧脚本备份在 `daily-news.bak.{timestamp}/`
- 回滚:删除新目录,重命名备份目录回 `daily-news/`
- cron 任务回滚:用旧 script 路径重新 `hermes cron update`

---

## 10. 验收标准

| 编号 | 验收项 | 验证方式 |
|------|--------|----------|
| AC1 | 三脚本独立运行输出正确 Markdown | `bash scripts/comprehensive.sh` 检查输出 |
| AC2 | `fetch_worker.py --type X` 输出合法 JSON | `python3 lib/fetch_worker.py --type comprehensive \| python3 -m json.tool` |
| AC3 | pytest 全绿(含所有 parser + dedup + cache 测试) | `cd tests && python3 -m pytest -v` |
| AC4 | comprehensive 执行 <30s | `time bash scripts/comprehensive.sh` |
| AC5 | tech-ai fetch_worker 执行 <60s | `time python3 lib/fetch_worker.py --type tech-ai` |
| AC6 | academic fetch_worker 执行 <90s | `time python3 lib/fetch_worker.py --type academic` |
| AC7 | 单源失败不影响其他源 | 手动断网某源,检查其他源正常输出 |
| AC8 | 缓存命中时跳过 HTTP | 二次运行,JSON 中 `cache_hit: true` |
| AC9 | 单次运行内去重有效 | 同一 type 运行中,无 URL 或标题 hash 重复条目;检查 items 列表 |
| AC10 | 健康检查输出各源状态 | `python3 lib/fetch_worker.py --health` |
| AC11 | 日志正确写入 | 检查 `~/.hermes/logs/news-*.log` |
| AC12 | 配置可调 | 修改 config.sh 条数,验证输出条数变化 |
| AC13 | 新增数据源可达 | `python3 lib/fetch_worker.py --health` 显示 7 个新源状态为 ok |
| AC14 | 新增源 parser 单元测试通过 | `cd tests && python3 -m pytest test_hn_parser.py test_producthunt_parser.py test_reddit_parser.py test_pubmed_parser.py -v`(4 个新源 parser 全绿) |
| AC15 | 内容安全清洗生效 | 构造含 `<script>` 标签的测试输入,验证 parser 输出已剥离 |
| AC16 | no-agent 推送到 QQ | `bash scripts/comprehensive.sh` 后检查 QQ 收到消息 |
| AC17 | agent 模式推送验证(手动) | 手动触发 daily-tech-ai cron,5 分钟内 QQ 收到中文 Markdown 日报;或手动执行 prompt 模板步骤验证 LLM 输出含翻译后的中文内容并调用 hermes send 成功 |

---

## 11. 风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|--------|----------|
| RSSHub 单点故障(rsshub.rssforever.com)影响多源 | 高 | comprehensive 的 5 源中 4 源依赖 RSSHub;重试 2 次 + 降级显示;config 预留 `RSSHUB_FALLBACK_URL`(本期不实现,下期配置备用实例) |
| agent 模式 LLM 翻译/推送失败 | 高 | Hermes cron 失败重试;可选配置 no-agent fallback cron(延迟 15 分钟,英文兜底推送);见 8.2 节 |
| arXiv RSS 偶发返回空内容 | 中 | 内容长度 <1000 字符时判定为空,降级显示 |
| GitHub API 限流(未认证 60 次/小时) | 中 | 缓存 1h TTL 减少请求;config 可配 `GITHUB_TOKEN` 提升至 5000 次/小时 |
| Reddit API 需 User-Agent 否则 403 | 低 | fetch 时固定带 `USER_AGENT` 头(已在 config 配置) |
| PubMed E-utilities 两步请求较慢 | 中 | esearch 与 esummary 串行执行(有依赖关系无法并行);但 PubMed 整体与其他源在 ThreadPoolExecutor 中并行 |
| /tmp 缓存被系统清理 | 低 | 缓存丢失时自动重新抓取,不影响功能;fetch_worker 启动时 clear_expired 清理过期文件 |
| agent 模式 LLM 翻译质量不稳定 | 中 | SKILL.md 中明确翻译规范;prompt 强调"保留专业术语,标题必译,摘要意译" |
| 内容安全:RSS/API 含恶意链接或 HTML 注入 | 中 | 所有 parser 统一执行 sanitize(剥离 HTML 标签、校验 URL 协议、转义 Markdown 特殊字符);见 3.3 节 |
| 双语言(Shell+Python)维护复杂度 | 低 | 接口清晰:Shell 仅调 fetch_worker + 格式化;Python 仅负责数据 |

---

## 12. 实施顺序建议

依赖关系:config 是基础;parsers 依赖 config;cache/dedup 独立;fetch_worker 集成 parsers/cache/dedup;脚本入口依赖 fetch_worker。单元测试与对应模块同步开发。

1. **阶段一:基础框架**(config/config.sh + lib/common.sh 骨架)— 可独立验证 config 加载
2. **阶段二:解析器 + 单元测试同步**(lib/parsers/* + tests/test_*_parser.py)— 从现有脚本逻辑抽取,每个 parser 配套测试
3. **阶段三:缓存与去重 + 单元测试**(lib/cache.py + lib/dedup.py + tests/test_cache.py + tests/test_dedup.py)
4. **阶段四:抓取入口集成**(lib/fetch_worker.py,集成 parsers/cache/dedup)— 端到端可验证
5. **阶段五:脚本入口**(scripts/comprehensive.sh + tech-ai.sh + academic.sh + tech-ai-fallback.sh + academic-fallback.sh)
6. **阶段六:新增数据源 + 单元测试**(parsers/hn_parser.py + pubmed_parser.py + reddit_parser.py + producthunt_parser.py + 对应测试)
7. **阶段七:部署与文档**(deploy.sh + README.md + SKILL.md 更新)

---

## 13. 环境要求

| 组件 | 版本要求 | 理由 |
|------|----------|------|
| Python | >= 3.10 | 使用 `dict \| None` 联合类型语法(3.10+);`list[dict]` 泛型(3.9+) |
| bash | >= 4.0 | 使用 `source` 命令、关联数组(可选) |
| Hermes Agent | >= 当前版本 | cron 调度 + `hermes send` + `hermes cron update` |
| pytest | >= 7.0 | 单元测试框架(开发期依赖,非运行时) |
| curl | 任意 | Shell 侧无直接 curl 调用,但 Hermes 环境通常预装 |

**Python 标准库依赖**:`urllib.request` / `json` / `re` / `xml.etree.ElementTree` / `concurrent.futures` / `hashlib` / `argparse` / `os` / `datetime` / `time` / `logging`

---

## 14. SKILL.md 内容大纲

`skill/SKILL.md` 是 Hermes Agent 的技能定义文件,供 agent 模式的 tech-ai / academic 日报使用:

- **技能名**:daily-news-editor
- **适用场景**:每日定时生成 AI 科技 / 学术日报并推送到 QQ
- **触发词**:"生成今日新闻日报" / "推送学术日报" / "查看今天的 AI 资讯"
- **执行规范**:
  1. 调用 `python3 ~/.hermes/scripts/daily-news/lib/fetch_worker.py --type {tech-ai|academic}` 获取数据
  2. 读取 JSON,翻译英文标题/摘要为中文(保留专业术语)
  3. 按 Markdown 格式输出(每源一个 ## 分节,每条目:编号+标题+摘要+链接)
  4. 结尾附今日洞察(3 条趋势归纳)
  5. 调用 `hermes send -f <md_file> -t <qq_target>` 推送
- **翻译规范**:标题必译,摘要意译,专业术语(LLM/Agent/GAN/Transformer)保留英文,人名保留英文
- **失败处理**:fetch_worker 失败时降级输出"数据源暂不可用";LLM 自身失败时由 fallback cron 兜底
