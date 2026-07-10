#!/bin/bash
# config.sh — 智讯日报系统统一配置
# 设计意图:Shell 与 Python 共享同一份配置,fetch_worker.py 通过 load_config() 内部 source 本文件

# ===== 数据源映射(源名必须与 SOURCE_REGISTRY 一致) =====
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

# ===== 超时(秒) =====
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
CACHE_TTL_RSS=1800        # 30 min,新闻更新快
CACHE_TTL_ARXIV=28800     # 8h,留余量避免 12:00 与 18:00 间隔 6h 的整点竞态
CACHE_TTL_GITHUB=3600     # 1h,趋势变化较快
CACHE_TTL_API=600         # 10 min,社区热点更新快
CACHE_RETENTION_HOURS=48  # 缓存文件与 .done 标记的保留时长
RSSHUB_FALLBACK_URL=""    # 备用 RSSHub 实例(本期留空,下期实现故障切换)

# ===== 日志 =====
LOG_DIR="${HOME}/.hermes/logs"
LOG_LEVEL="INFO"
# TIMESTAMP/DATE 由 common.sh 在 load_config 后生成:
#   TIMESTAMP="$(date +%Y-%m-%dT%H:%M:%S%z)"  # ISO8601,与日志格式一致
#   DATE="$(date +%Y年%-m月%-d日)"
# 备份目录用 YYYYMMDDHHmmss 格式(见 deploy.sh),与 TIMESTAMP(ISO8601)区分用途

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
