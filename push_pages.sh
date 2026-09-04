#!/bin/bash
# 把 build/ 推送到 GitHub Pages 的 gh-pages 分支（服务器端运行）。
# 认证方式：仓库 Deploy Key（/root/.ssh/zrfan_deploy），只授权本仓库，不存账号 token。
set -e
REPO_DIR=/opt/zrfan-calendar/gh-pages-repo
BUILD_DIR=/opt/zrfan-calendar/build
export GIT_SSH_COMMAND="ssh -i /root/.ssh/zrfan_deploy -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "[push] 首次 clone gh-pages 分支"
    rm -rf "$REPO_DIR"
    git clone --branch gh-pages --single-branch --depth 1 git@github.com:rayassassin/zrfan-calendar.git "$REPO_DIR"
fi

cd "$REPO_DIR"
git fetch origin gh-pages --depth 1
git reset --hard origin/gh-pages >/dev/null
# 清空除 .git 外的内容
find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
# 复制最新 build
cp -r "$BUILD_DIR"/. .
git add -A
if git diff --cached --quiet; then
    echo "[push] 内容无变化，跳过"
    exit 0
fi
git -c user.name="zrfan-bot" -c user.email="bot@zrfan.local" commit -m "chore: update calendar $(date '+%Y-%m-%d %H:%M')" >/dev/null
git push origin gh-pages
echo "[push] 已推送到 gh-pages"
