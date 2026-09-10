#!/bin/bash
# 每日定时任务入口：抓取生成日历 -> 推送到 GitHub Pages。
# 由 crontab 调用（每天 0 点主更新）。整个链路都在国内服务器完成，
# 绕开 GitHub Actions 连不上 zrfan.com 的问题。
# 透传参数给 main.py，例如 catchup_if_missed.sh 会追加 --force 强制重抓。
set -uo pipefail

DIR=/opt/zrfan-calendar
cd "$DIR" || { echo "[FATAL] 无法进入 $DIR"; exit 1; }

# ---------- 磁盘与日志守卫（避免磁盘写满导致整机卡死）----------
mkdir -p "$DIR/logs" "$DIR/cache" "$DIR/raw"

# cron.log 超过 5MB 就截断保留最后 2000 行
if [ -f "$DIR/logs/cron.log" ]; then
    SIZE=$(stat -c%s "$DIR/logs/cron.log" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt 5242880 ]; then
        tail -n 2000 "$DIR/logs/cron.log" > "$DIR/logs/cron.log.tmp" \
            && mv "$DIR/logs/cron.log.tmp" "$DIR/logs/cron.log"
        echo "[$(date '+%F %T')] cron.log 已轮转（原 ${SIZE} 字节）"
    fi
fi

# raw/ 缓存只保留最近 30 个文件
find "$DIR/raw" -type f -name '*.html' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | tail -n +31 | awk '{print $2}' | xargs -r rm -f

# 磁盘使用率超过 90% 只告警不中断（避免抓不到数据）
USED=$(df --output=pcent "$DIR" 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "${USED:-}" ] && [ "$USED" -ge 90 ]; then
    echo "[$(date '+%F %T')] [WARN] 磁盘使用率 ${USED}%，请及时清理！"
    du -sh "$DIR"/* 2>/dev/null | sort -rh | head -5
fi

# ---------- 正式流程 ----------
/usr/bin/python3 main.py -n 7 "$@"
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "[$(date '+%F %T')] [ERROR] main.py 退出码 $RC，跳过推送"
    exit "$RC"
fi

bash "$DIR/push_pages.sh"
