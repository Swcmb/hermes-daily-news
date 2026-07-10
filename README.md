# 智讯日报 — Hermes Daily News System

每日自动采集并推送三大日报的完整系统，运行在 Hermes Agent 的 cron 调度之上。

## 日报一览

| 类型 | 时间 | 模式 | 数据源 |
|------|------|------|--------|
| 📰 综合新闻 | 08:00 | 纯 Shell 脚本 | 知乎热榜、36氪、牛客、GitHub Trending |
| 📡 AI科技 | 12:00 | Agent 模式（LLM 翻译） | arXiv cs.AI/cs.LG、GitHub、36氪 |
| 🧬 学术前沿 | 18:00 | Agent 模式（LLM 翻译） | arXiv cs.AI/stat.ML/q-bio.GN/q-bio.QM |

## 文件结构

```
hermes-daily-news/
├── scripts/
│   ├── comprehensive-news-daily.sh   # 综合新闻（纯 Shell）
│   ├── tech-ai-daily.sh              # AI科技（Shell + Python 解析）
│   └── academic-daily.sh             # 学术前沿（Shell + Python 解析）
├── skill/
│   └── SKILL.md                      # Hermes skill 定义
└── README.md
```

## 设计原则

- **中文优先**：所有日报内容为简体中文，英文源（arXiv、GitHub）标题/摘要经翻译后呈现
- **防卡死**：每源 8-30s 超时，整脚本 50-150s 超时保护
- **失败兜底**：单源失败不影响其他源，友好降级显示"暂不可用"
- **多源并行**：独立 fetch，互不阻塞

## 数据源

| 源 | 用途 |
|----|------|
| rss.arxiv.org/rss/cs.AI | AI 论文 |
| rss.arxiv.org/rss/cs.LG | 机器学习论文 |
| rss.arxiv.org/rss/stat.ML | 统计学习 |
| rss.arxiv.org/rss/q-bio.GN | 基因组学 |
| rss.arxiv.org/rss/q-bio.QM | 定量生物学 |
| rsshub.rssforever.com/36kr/newsflashes | 36氪快讯 |
| rsshub.rssforever.com/nowcoder/recommend | 牛客热议 |
| api.github.com/search/repositories | GitHub 仓库搜索 |
| www.zhihu.com/rss | 知乎热榜 |

## 部署

```bash
# 1. 放置脚本
cp scripts/*.sh ~/.hermes/scripts/daily-news/

# 2. 注册 cron 任务（Hermes Agent）
hermes cron create --name "daily-comprehensive-news" --schedule "0 8 * * *" --script "daily-news/comprehensive-news-daily.sh" --no-agent
hermes cron create --name "daily-tech-ai" --schedule "0 12 * * *" --prompt "..." --skill daily-news-editor
hermes cron create --name "daily-academic" --schedule "0 18 * * *" --prompt "..." --skill daily-news-editor
```

## 许可

CC BY-NC 4.0 — 署名-非商业使用