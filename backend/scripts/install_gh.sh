#!/usr/bin/env bash
# Установка GitHub CLI (gh) + авторизация через PAT.
#
# Запуск:
#   bash /opt/menugen/backend/scripts/install_gh.sh

set -euo pipefail

if command -v gh >/dev/null 2>&1; then
  echo "gh уже установлен: $(gh --version | head -1)"
else
  echo "== installing gh =="
  # Официальный путь из docs: https://github.com/cli/cli/blob/trunk/docs/install_linux.md
  (type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
    && sudo mkdir -p -m 755 /etc/apt/keyrings \
    && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && sudo apt update \
    && sudo apt install gh -y
  rm -f "$out"
fi

echo
echo "== version =="
gh --version | head -1

echo
echo "== auth =="
if gh auth status >/dev/null 2>&1; then
  gh auth status
else
  echo "Авторизуюсь через PAT из ~/.git-credentials..."
  # Достаём PAT который сохранили ранее
  CRED_FILE="${HOME}/.git-credentials"
  if [ ! -f "$CRED_FILE" ]; then
    echo "Нет ~/.git-credentials. Запусти 'gh auth login' вручную."
    exit 1
  fi
  PAT="$(grep -oE 'https://[^:]+:([^@]+)@github\.com' "$CRED_FILE" | head -1 | sed -E 's|.*:([^@]+)@.*|\1|')"
  if [ -z "$PAT" ]; then
    echo "Не нашёл PAT в ~/.git-credentials. Запусти 'gh auth login' вручную."
    exit 1
  fi
  echo "$PAT" | gh auth login --hostname github.com --git-protocol https --with-token
  unset PAT
  gh auth status
fi

echo
echo "== quick test =="
REPO="$(git -C /opt/menugen remote get-url origin | sed -E 's|.*[:/]([^/]+/[^/.]+)(\.git)?$|\1|')"
echo "Repo: $REPO"
gh run list --repo "$REPO" --branch main --limit 3
