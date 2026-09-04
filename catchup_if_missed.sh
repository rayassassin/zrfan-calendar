#!/bin/bash
# 每天 6:00 兜底更新：仅当 0 点那轮没有抓到「当天日期」的指南文章时才补跑一次。
#
# 背景：zrfan.com 每天更新一篇当日指南，但发布时间不固定——0 点主更新时
# 当天的文章可能还没发布（抓到的是昨天的）。本脚本在 6 点再检查一次：
#   - state/latest_article_date == 今天  → 0 点已抓到当天文章，直接跳过
#   - 否则                                → 用 --force 绕过缓存强制重抓补一次
cd /opt/zrfan-calendar
TODAY=$(date '+%Y-%m-%d')
LATEST=$(cat state/latest_article_date 2>/dev/null || echo '')

if [ "$LATEST" = "$TODAY" ]; then
    echo "[6点兜底] 0点已抓到当天($TODAY)指南，无需补跑"
    exit 0
fi

echo "[6点兜底] 当天($TODAY)指南尚未出现（0点抓到的最新是 ${LATEST:-无}），强制重抓补一次"
bash /opt/zrfan-calendar/update_and_push.sh --force
