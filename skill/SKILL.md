---
name: daily-news-editor
description: 智讯日报主编 - 每日自动推送综合新闻/科技AI/学术三大日报到 QQ bot
version: 1.0.0
author: 智讯日报主编 Agent
---

# 智讯日报主编 Skill

## 功能

每日自动从多源采集并推送三大类日报到用户 QQ：

| 日报类型 | 推送时间 | 数据源 |
|---------|---------|--------|
| 综合新闻日报 | 每日 08:00 | 知乎热榜 · 36氪快讯 · 牛客热议 · GitHub Trending |
| 科技日报（AI 专题） | 每日 12:00 | arXiv cs.AI/cs.LG · GitHub · 36氪 AI 关键词 |
| 学术日报（AI+GNN+生物信息学） | 每日 18:00 | arXiv cs.AI/stat.ML/q-bio.GN/q-bio.QM |

## 设计原则

- **中文优先**：推送用户时，所有内容必须为中文（简体）。英文源（arXiv、GitHub 等）的标题和摘要必须翻译后呈现。用户明确要求"用中文"时此规则强制执行
- **内容呈现用 agent 模式**：当用户要求中文输出时（论文标题/摘要翻译），必须切换到 agent 模式（no_agent=false），让 LLM 负责搜索 arXiv 并翻译为中文。学术日报、科技AI日报默认走 agent 模式
- **综合新闻仍用 no-agent 模式**（shell 脚本 + cron no_agent=true）：综合新闻数据源（知乎热榜、36氪）本身为中文，shell 脚本采集即可，避免 LLM agent loop 卡死
- **多源并行 + 严格超时**：单源 fetch 8-20s，整脚本 50-150s
- **失败兜底**：单源失败不影响其他源；输出友好降级

## 关键路径

- 脚本目录：~/.hermes/scripts/daily-news/
  - `comprehensive-news-daily.sh` - 综合新闻
  - `tech-ai-daily.sh` - 科技AI
  - `academic-daily.sh` - 学术
- 日志：~/.hermes/logs/news-*.log
- Hermes cron job IDs：在 `hermes cron list` 中查看（命名 daily-comprehensive-news / daily-tech-ai / daily-academic）

手动触发日报

立即生成并发送某类日报到当前对话：

```bash
bash ~/.hermes/scripts/daily-news/comprehensive-news-daily.sh > /tmp/daily.md
hermes cron run <job-id>   # 例如 hermes cron run 99468eb0a050
```

或直接执行脚本查看输出：
```bash
bash ~/.hermes/scripts/daily-news/comprehensive-news-daily.sh
```

指定目标推送：
```bash
bash ~/.hermes/scripts/daily-news/comprehensive-news-daily.sh > /tmp/daily.md
hermes send -f /tmp/daily.md -t qqbot:AC6557CF43ED1A86EA5C1A17C72B5B6D
```
```

## 查看日报任务状态

```bash
hermes cron list | grep daily-news
```

## 修改推送时间

```bash
# 查看任务 ID
hermes cron list

# 修改时间（示例：把综合新闻改到 07:30）
hermes cron edit <job-id> --schedule "30 7 * * *"
```

## 数据源说明

| 源 | URL | 备注 |
|----|-----|------|
| 知乎热榜 | https://www.zhihu.com/rss | 国内热点，偶有不可用 |
| 36氪快讯 | rsshub.rssforever.com/36kr/newsflashes | 财经科技 |
| 牛客推荐 | rsshub.rssforever.com/nowcoder/recommend | 行业/IT |
| GitHub API | api.github.com/search/repositories | Trending |
| arXiv cs.AI | rss.arxiv.org/rss/cs.AI | AI 论文 |
| arXiv cs.LG | rss.arxiv.org/rss/cs.LG | 机器学习 |
| arXiv stat.ML | rss.arxiv.org/rss/stat.ML | 统计 ML |
| arXiv q-bio.GN | rss.arxiv.org/rss/q-bio.GN | 基因组学 |
| arXiv q-bio.QM | rss.arxiv.org/rss/q-bio.QM | 定量生物学 |

> 注：使用 rss.arxiv.org 而非 export.arxiv.org（后者在国内易被墙）

## 各日报 cron 模式一览

| 日报 | 时间 | 模式 | 原因 |
|------|------|------|------|
| 综合新闻 | 08:00 | no_agent + script | 中文数据源，shell 采集即可 |
| 科技AI | 12:00 | agent（no_agent=false） | 需英文→中文翻译 |
| 学术 | 18:00 | agent（no_agent=false） | 需英文→中文翻译 |

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 整日报推送为空 | 脚本超时或语法错误 | `bash -x ~/.hermes/scripts/daily-news/xxx.sh` 调试 |
| 某源显示"暂不可用" | 网络抖动/源宕机 | 等待下次执行（脚本每源独立超时） |
| 推送延迟超过 5 分钟 | 脚本执行 + 队列等待 | 检查 `hermes cron list` 的 last_run_at |
| 任务被禁用 | `enabled: false` | `hermes cron resume <id>` |

## Pitfalls

- **Skill 文档 ≠ 实际 cron 命名**：技能描述中的 job 命名可能过期，务必以 `hermes cron list` 的实际注册为准
- **`hermes send` 不是管道命令**：不能 `script.sh | hermes send`，应先用 `hermes cron run <id>` 或通过 `-f` 指定文件
- **arXiv 用 rss.arxiv.org**：export.arxiv.org 在国内可能被墙，脚本中已使用 rss.arxiv.org
- **从 no-agent 模式切换到 agent 模式时，必须同时清除 script 和 no_agent 字段**：只改 no_agent=false 但保留 script 字段会导致 cron 仍以脚本模式运行，prompt 不会被使用。正确做法：`cronjob update --no_agent=false --script=""` 或设置 script 为空字符串
- **已切换到 agent 模式的 cron 不要改回 no-agent**：agent 模式的 prompt 包含了翻译指令，改回 no-agent 后会丢失翻译能力
- **No-agent 模式绕过 LLM 翻译指令**：no_agent=true + script 的 cron 任务不加载任何 skill，不经过 LLM，所有输出完全由脚本决定。因此英文源（arXiv）的论文标题/摘要在 no-agent 模式下永远保持英文——中文翻译必须在 shell 脚本中硬编码或调用翻译 API，不能依赖 agent prompt。如需中文输出，必须切到 agent 模式（no_agent=false，清除 script，在 prompt 中写明「所有内容必须用中文」）
- **综合新闻暂不切换 agent 模式**：因其数据源（知乎、36氪）本身为中文，shell 脚本模式更稳定可靠
- **交互式 cron（attach_to_session=true）无法自调度子任务**：attach_to_session 的 cron 在用户回复后进入新的 agent session，此时该 session 不能动态创建新的 cron job。如需「先询问用户再定时执行」的流程（如 19:00 问座位 → 19:18:30 自动预约），正确做法是：ask cron 用 attach_to_session=true 发问 → 用户回复后，在回复处理逻辑中用 `cronjob create` 创建一个 one-shot 定时任务执行后续操作

## 输出格式参考

详见各脚本内的 cat <<EOF 块。标准结构：

- 标题：📰/📡/🧬 智讯·XX日报 — 日期
- 分节：## 分类
- 列表：编号 + 标题 + 摘要 + 链接
- 结尾：洞察/提示/趋势观察
- 时间线占位：可由 Agent 后续用 Mermaid 渲染

## 何时调用此 Skill

当用户表达以下意图时自动激活：
- "生成今日新闻日报"
- "推送学术日报"
- "查看今天的 AI 资讯"
- "现在跑一下日报"
- "今日日报怎么样"

也可作为每日定时任务的执行体（已在 cron 中配置）。
