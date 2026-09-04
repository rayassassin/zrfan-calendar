#!/bin/bash
# 每日定时任务入口：抓取生成日历 -> 推送到 GitHub Pages。
# 由 crontab 调用。整个链路都在国内服务器完成，绕开 GitHub Actions 连不上 zrfan.com 的问题。
cd /opt/zrfan-calendar
/usr/bin/python3 main.py -n 7
bash /opt/zrfan-calendar/push_pages.sh
