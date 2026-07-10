#!/bin/bash
# 每日 06:00 曲阜天气推送
CITY="曲阜"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

# 用 wttr.in 获取天气（带 emoji 的简洁版）
WEATHER=$(curl -s "wttr.in/Qufu?format=%c+%t+%w+%h&lang=zh" 2>/dev/null)

# 获取三天预报概要
FORECAST=$(curl -s "wttr.in/Qufu?format=3&lang=zh" 2>/dev/null | head -5)

echo "🌤 $CITY 天气预报 — $TIMESTAMP"
echo ""
echo "$WEATHER"
echo ""
echo "$FORECAST"