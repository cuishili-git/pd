#!/usr/bin/env bash
# 把本仓库一键推送到 GitHub（免 token，走 SSH-over-443 隧道）
#
# 背景：本机直连 github.com 的 22/443 会被 reset，git credential 也取不到 token；
# 但环境提供本地 HTTP 代理，且已有 ~/.ssh/id_ed25519 加进了 GitHub 账户。
# 因此用 OpenSSH 的 ProxyCommand 走 HTTP CONNECT 隧道到 ssh.github.com:443。
# 代理端口是会话级的（实测 62939 → 55517 → 58893），所以由 Python 脚本
# 自动从 HTTPS_PROXY 读取，不写死端口。
#
# 用法（在任意目录执行均可）：
#   bash D:/workbuddy/docs/pd/tools/push.sh
#   SKIP_PUSH=1 bash tools/push.sh                 # 只提交不推送
#   REPO=cuishili-git/pd BRANCH=main MSG="docs: xxx" bash tools/push.sh
#
# 认证自检：
#   ssh -T -p 443 -o ProxyCommand="python D:/workbuddy/docs/pd/tools/ssh-https-proxy.py ssh.github.com 443" git@ssh.github.com
#   → Hi <user>! You've successfully authenticated, but GitHub does not provide shell access.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${REPO:-cuishili-git/pd}"
BRANCH="${BRANCH:-main}"
USER_NAME="${GIT_USER:-cuishili-git}"
USER_EMAIL="${GIT_EMAIL:-13370616627@163.com}"
MSG="${MSG:-docs: 更新局放信号源 V0 教程 @ $(date '+%Y-%m-%d %H:%M')}"
PROXY_PY="$(cygpath -m "$ROOT/tools/ssh-https-proxy.py" 2>/dev/null || echo "$ROOT/tools/ssh-https-proxy.py")"

echo "仓库目录 : $ROOT"
echo "目标     : $REPO / $BRANCH"

# --- 0. 前置检查 -----------------------------------------------------------
[ -f "$ROOT/tools/ssh-https-proxy.py" ] || { echo "ERROR: 缺 tools/ssh-https-proxy.py" >&2; exit 1; }
command -v python >/dev/null   || { echo "ERROR: python 不在 PATH" >&2; exit 1; }
command -v git >/dev/null      || { echo "ERROR: git 不在 PATH" >&2; exit 1; }
if [ -z "${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-}}}}" ]; then
  echo "提示: 未设置 HTTPS_PROXY，隧道脚本会尝试直连 ssh.github.com:443"
else
  echo "代理     : ${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-$http_proxy}}}"
fi

# --- 1. 仓库初始化（幂等） -------------------------------------------------
if [ ! -d "$ROOT/.git" ]; then
  echo "[1/4] git init -b $BRANCH"
  git -C "$ROOT" init -b "$BRANCH" -q
fi

git -C "$ROOT" config user.name  "$USER_NAME"
git -C "$ROOT" config user.email "$USER_EMAIL"
git -C "$ROOT" config core.sshCommand \
  "ssh -p 443 -o ProxyCommand=\"python $PROXY_PY ssh.github.com 443\" -o StrictHostKeyChecking=accept-new -o BatchMode=yes"

REMOTE_URL="ssh://git@ssh.github.com:443/$REPO.git"
if git -C "$ROOT" remote get-url origin >/dev/null 2>&1; then
  git -C "$ROOT" remote set-url origin "$REMOTE_URL"
else
  git -C "$ROOT" remote add origin "$REMOTE_URL"
fi

# --- 2. 提交 ---------------------------------------------------------------
echo "[2/4] git add -A"
git -C "$ROOT" add -A

if git -C "$ROOT" diff --cached --quiet; then
  echo "      没有新改动，跳过 commit"
else
  echo "[3/4] git commit"
  git -C "$ROOT" commit -q -m "$MSG"
  git -C "$ROOT" log -1 --oneline
fi

# --- 3. 推送 ---------------------------------------------------------------
if [ "${SKIP_PUSH:-0}" = "1" ]; then
  echo "[4/4] SKIP_PUSH=1，已跳过推送"
  exit 0
fi

echo "[4/4] 推送到 $REMOTE_URL"
# 空仓库首次推送不需要 force；若远端有无关历史，脚本会明确失败而不会覆盖。
git -C "$ROOT" push -u origin "$BRANCH" 2>&1 | tail -12

echo ""
echo "完成: https://github.com/$REPO/tree/$BRANCH"
