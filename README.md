# hermes-daily-news

智讯日报——每日自动推送综合新闻、AI 科技、学术前沿三大日报到 QQ。

v2.1 架构：Shell + Python 混合，18 数据源，132 测试全绿。

## 项目结构

```
hermes-daily-news/
├── config/config.sh       # 配置（数据源 URL/缓存 TTL/QQ_TARGET）
├── lib/                   # 核心库
│   ├── fetch_worker.py    # 并行抓取入口
│   ├── format_markdown.py # JSON → Markdown
│   ├── cache.py           # 文件缓存
│   ├── dedup.py           # 去重
│   ├── common.sh          # Shell 公共库
│   └── parsers/           # 8 个数据源解析器
├── scripts/               # Shell 脚本（cron 入口）
├── tests/                 # 单元测试（132 个）
├── skill/SKILL.md         # 技能定义
└── deploy.sh              # 部署脚本
```

## 快速开始

1. 部署后需手动修改 `config/config.sh` 填入真实 `QQ_TARGET`
2. 运行 `bash deploy.sh` 部署
3. 手动测试：`bash scripts/comprehensive.sh`

## 数据源

| 日报 | 源数 | 模式 | 数据源 |
|------|------|------|--------|
| 综合新闻 | 5 | no-agent | 知乎/36氪/牛客/微博/百度 |
| AI 科技 | 8 | agent | arXiv/GitHub/HN/PH/Reddit/36kr AI/TechCrunch AI |
| 学术前沿 | 7 | agent | arXiv/PubMed/bioRxiv |

## 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QQ_TARGET` | qqbot:YOUR_BOT_TOKEN_HERE | QQ Bot 推送目标 |
| `GITHUB_TOKEN` | （空） | 可选，填入提升 API 限流至 5000 次/小时 |

修改配置后无需改代码，下次 cron 执行自动生效。

## 测试

```bash
python -m pytest
```

## License

MIT
