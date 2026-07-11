#!/bin/bash
# 曲阜气象预警监控
# 从中国天气网抓取预警信息
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

# 曲阜的天气预警页面
ALERT=$(curl -s "http://www.weather.com.cn/weather1d/101120711.shtml" 2>/dev/null | grep -oP 'alert|预警|暴雨|台风|寒潮|大风|高温|雷电|冰雹|大雾|霜冻|暴雪' | head -5)

# 备用：通过 wttr.in 看是否有预警
WTTR=$(curl -s "wttr.in/Qufu?format=%t&lang=zh" 2>/dev/null)

if [ -n "$ALERT" ]; then
    echo "⚠️ 曲阜气象预警 — $TIMESTAMP"
    echo "$ALERT"
    echo ""
    echo "详情：http://www.weather.com.cn/weather1d/101120711.shtml"
fi