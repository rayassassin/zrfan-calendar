#!/usr/bin/env bash
# zrfan 刷卡指南日历 —— 服务器一键部署
#
# 用法（在目标服务器上执行）：
#   bash deploy.sh [安装目录] [端口]
# 例：
#   bash deploy.sh /opt/zrfan-calendar 8080
#
# 脚本只做这些事：拷贝代码 -> 试跑一次 -> 启动静态服务 -> 写 crontab。
# 定时策略固定为「0 点主更新 + 6 点兜底」（见 catchup_if_missed.sh）。
# 不会改动系统与 nginx 的既有配置；没有 nginx 时退化为 Python 静态服务。
# 注意：推送到 GitHub Pages 需先在服务器配好仓库 Deploy Key（见 README 方案 B）。
set -euo pipefail

INSTALL_DIR="${1:-/opt/zrfan-calendar}"
PORT="${2:-8080}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

say() { printf '\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
ok() { printf '\033[1;32m[✓] %s\033[0m\n' "$*"; }

say "检查依赖"
command -v python3 >/dev/null || { echo "需要 python3"; exit 1; }
command -v curl >/dev/null || { echo "需要 curl"; exit 1; }
PY="$(command -v python3)"
ok "python3: $($PY -V 2>&1), curl: $(command -v curl)"

say "安装到 $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"/{cache,raw,logs}
for f in crawler.py parser.py ics_gen.py page.py validate.py main.py serve.py \
         push_pages.sh update_and_push.sh catchup_if_missed.sh; do
  cp "$SRC_DIR/$f" "$INSTALL_DIR/$f"
done
chmod +x "$INSTALL_DIR"/*.sh
mkdir -p "$INSTALL_DIR/state"
ok "代码已就位"

say "首次抓取并生成（约需 10-20 秒）"
cd "$INSTALL_DIR"
if ! $PY main.py -n 7; then
  warn "首次生成失败，检查网络是否能访问 www.zrfan.com"
  exit 1
fi
ok "已生成 $(find build/ics -name '*.ics' | wc -l) 个日历文件"

say "启动静态服务"
if [ -d /etc/systemd/system ] && command -v systemctl >/dev/null 2>&1; then
  cat > /etc/systemd/system/zrfan-calendar.service <<EOF
[Unit]
Description=zrfan card guide calendar
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$PY $INSTALL_DIR/serve.py $PORT $INSTALL_DIR/build
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now zrfan-calendar.service
  sleep 1
  if systemctl is-active --quiet zrfan-calendar.service; then
    ok "已通过 systemd 启动（开机自启）"
    USING_SYSTEMD=1
  else
    warn "systemd 启动失败，改用 nohup"
    USING_SYSTEMD=0
  fi
else
  USING_SYSTEMD=0
fi

if [ "$USING_SYSTEMD" = "0" ]; then
  cd "$INSTALL_DIR"
  nohup "$PY" serve.py "$PORT" "$INSTALL_DIR/build" >> logs/serve.log 2>&1 &
  echo $! > "$INSTALL_DIR/.serve.pid"
  sleep 1
  ok "已用 nohup 启动，PID $(cat "$INSTALL_DIR/.serve.pid")"
fi

say "配置定时更新（0 点主更新 + 6 点兜底）"
CRON_MAIN="0 0 * * * cd $INSTALL_DIR && bash $INSTALL_DIR/update_and_push.sh >> $INSTALL_DIR/logs/cron.log 2>&1"
CRON_CATCH="0 6 * * * cd $INSTALL_DIR && bash $INSTALL_DIR/catchup_if_missed.sh >> $INSTALL_DIR/logs/cron.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'zrfan-calendar\|update_and_push\|catchup_if_missed' ; echo "$CRON_MAIN" ; echo "$CRON_CATCH" ) | crontab -
ok "crontab 已写入："
crontab -l | grep -E 'update_and_push|catchup_if_missed' | sed 's/^/    /'
echo "    说明：0 点主更新；若当天指南还没发布，6 点会自动补抓一次"

IP="$(curl -s --max-time 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
say "完成"
echo
echo "    预览页：   http://${IP}:${PORT}/"
echo "    浦发日历： http://${IP}:${PORT}/ics/spdb.ics"
echo
warn "重要：Google 日历只接受 HTTPS 订阅源！"
echo "    当前是 http，Google 日历会拒绝。请二选一："
echo "    1) 用 certbot 申请证书 + nginx 反代（见 nginx.conf.example）"
echo "    2) 用免费的 GitHub Pages / Cloudflare Pages 托管（见 README.md）"
echo
warn "若用防火墙，记得放行 ${PORT} 端口"
