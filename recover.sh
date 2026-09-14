#!/bin/bash
# ============================================================================
# 灾难恢复：当云服务器上的 /opt/zrfan-calendar 被清空（重装系统、误删）后，
# 在本地一条命令重建整条链路。
#
# 用法：
#   bash recover.sh <host> [port] [password]
#   ZRFAN_SSH_PASS=xxx bash recover.sh <host>
#
# 前置条件：
#   1. 本机有 expect（macOS 自带）
#   2. Deploy Key 私钥备份存在，以下任一路径：
#        - 项目内 .secrets/zrfan_deploy（推荐，已 gitignore）
#        - ~/.ssh/zrfan_calendar_deploy
#      若都没有，脚本会提示，需要重新生成并用 GitHub PAT 注册新的 Deploy Key
#
# 恢复内容：代码上传 → Deploy Key 恢复 → crontab 重建 → 试跑验证
#
# ⚠️ 安全：密码一律通过参数或 ZRFAN_SSH_PASS 环境变量传入，
#          不写入本文件，避免随代码提交泄露。
# ============================================================================
set -uo pipefail

HOST="${1:-}"
PORT="${2:-2525}"
PASS="${3:-${ZRFAN_SSH_PASS:-}}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$HOST" ] || [ -z "$PASS" ]; then
    echo "用法: bash recover.sh <host> [port] [password]"
    echo "      ZRFAN_SSH_PASS=xxx bash recover.sh <host>"
    echo
    echo "例:   ZRFAN_SSH_PASS='你的密码' bash recover.sh 59.110.138.163 2525"
    exit 1
fi
INSTALL_DIR=/opt/zrfan-calendar
TMP_TAR=/tmp/zrfan-recover.tar.gz

# Deploy Key 私钥备份位置，按优先级查找：
#   1. 项目内 .secrets/（已 gitignore，推荐）
#   2. ~/.ssh/（标准位置；注意 macOS 会对该目录做隐私保护）
KEY_BACKUP=""
for _p in "$SRC_DIR/.secrets/zrfan_deploy" "$HOME/.ssh/zrfan_calendar_deploy"; do
    [ -f "$_p" ] && { KEY_BACKUP="$_p"; break; }
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
say()  { printf '\n\033[1m%s\033[0m\n' "$1"; }

# ---------- SSH / SCP 辅助（expect 自动填密码） ----------
cat > /tmp/_recover_ssh.exp <<'EXP'
#!/usr/bin/expect -f
set timeout 300
set cmd [lindex $argv 0]
spawn ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
    -o NumberOfPasswordPrompts=1 -p [lindex $argv 1] root@[lindex $argv 2] $cmd
expect {
    -re "(P|p)assword:" { send "[lindex $argv 3]\r"; exp_continue }
    -re "yes/no" { send "yes\r"; exp_continue }
    timeout { puts "TIMEOUT"; exit 1 }
    eof
}
catch wait result
EXP

cat > /tmp/_recover_scp.exp <<'EXP'
#!/usr/bin/expect -f
set timeout 300
spawn scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
    -o NumberOfPasswordPrompts=1 -P [lindex $argv 0] [lindex $argv 1] root@[lindex $argv 2]:[lindex $argv 3]
expect {
    -re "(P|p)assword:" { send "[lindex $argv 4]\r"; exp_continue }
    timeout { puts "TIMEOUT"; exit 1 }
    eof
}
catch wait result
EXP
chmod +x /tmp/_recover_ssh.exp /tmp/_recover_scp.exp

rsh()  { /tmp/_recover_ssh.exp "$1" "$PORT" "$HOST" "$PASS"; }
rscp() { /tmp/_recover_scp.exp "$PORT" "$1" "$HOST" "$2" "$PASS"; }

# ---------- 0. 连通性 ----------
say "[0/5] 检查服务器连通性"
if ! nc -z -w 8 "$HOST" "$PORT" 2>/dev/null; then
    warn "无法连接 $HOST:$PORT —— 请确认服务器已开机、安全组放行该端口"
    exit 1
fi
ok "$HOST:$PORT 可达"

# ---------- 1. 打包代码 ----------
say "[1/5] 打包本地代码"
cd "$SRC_DIR"
# COPYFILE_DISABLE 抑制 macOS 的 ._ 资源分叉；--no-xattrs 抑制扩展属性头告警
COPYFILE_DISABLE=1 tar czf "$TMP_TAR" --no-xattrs \
    crawler.py parser.py ics_gen.py page.py validate.py main.py serve.py \
    deploy.sh push_pages.sh update_and_push.sh catchup_if_missed.sh \
    README.md nginx.conf.example .gitignore 2>/dev/null
ok "已打包：$(du -h "$TMP_TAR" | cut -f1)"

# ---------- 2. 上传并解压 ----------
say "[2/5] 上传并解压到 $INSTALL_DIR"
rscp "$TMP_TAR" /tmp/ >/dev/null 2>&1
rsh "mkdir -p $INSTALL_DIR && cd $INSTALL_DIR && tar xzf /tmp/zrfan-recover.tar.gz && \
     find . -name '._*' -delete && rm -f /tmp/zrfan-recover.tar.gz && \
     mkdir -p cache raw logs state && chmod +x *.sh && \
     echo '  ✓ 代码就位'" | tail -2

# ---------- 3. 恢复 Deploy Key ----------
say "[3/5] 恢复 Deploy Key"
if [ -f "$KEY_BACKUP" ]; then
    rsh "mkdir -p /root/.ssh && chmod 700 /root/.ssh" >/dev/null 2>&1
    rscp "$KEY_BACKUP" /root/.ssh/zrfan_deploy >/dev/null 2>&1
    rsh "chmod 600 /root/.ssh/zrfan_deploy && \
         ssh -i /root/.ssh/zrfan_deploy -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
             -o BatchMode=yes -T git@github.com 2>&1 | head -2" | tail -2
else
    warn "未找到私钥备份 $KEY_BACKUP"
    warn "需要重新生成 Deploy Key 并用 GitHub PAT 注册（见 README「灾难恢复」章节）"
fi

# ---------- 4. 重建 crontab ----------
say "[4/5] 重建 crontab"
cat > /tmp/_recover_cron.txt <<'CRON'
0 0 * * * cd /opt/zrfan-calendar && bash /opt/zrfan-calendar/update_and_push.sh >> /opt/zrfan-calendar/logs/cron.log 2>&1
0 6 * * * cd /opt/zrfan-calendar && bash /opt/zrfan-calendar/catchup_if_missed.sh >> /opt/zrfan-calendar/logs/cron.log 2>&1
CRON
rscp /tmp/_recover_cron.txt /tmp/cron.txt >/dev/null 2>&1
rsh "crontab /tmp/cron.txt && rm -f /tmp/cron.txt && systemctl is-active cron && crontab -l" | tail -4

# ---------- 5. 试跑验证 ----------
say "[5/5] 试跑一次完整流程（抓取 → 生成 → 推送）"
rsh "cd $INSTALL_DIR && bash update_and_push.sh 2>&1 | tail -8" | tail -10

say "恢复完成"
echo "  预览页：https://rayassassin.github.io/zrfan-calendar/"
echo "  日志：  $HOST:$INSTALL_DIR/logs/cron.log"
