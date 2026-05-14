#!/usr/bin/env bash
# DIAG: git auth setup
ROOT="${PROJECT_DIR:-/opt/menugen}"
cd "$ROOT"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "1. git remote -v"
git remote -v

hr "2. credential helper"
git config --global --get credential.helper || echo "(none)"
git config --get credential.helper || echo "(none, repo level)"

hr "3. user.name / user.email"
git config user.name
git config user.email

hr "4. ssh keys present?"
ls -la ~/.ssh/ 2>/dev/null | grep -E "id_|config" || echo "no ssh keys"

hr "5. test SSH access to github"
ssh -T -o StrictHostKeyChecking=no -o ConnectTimeout=5 git@github.com 2>&1 | head -5

hr "6. current branch + status"
git rev-parse --abbrev-ref HEAD
git log --oneline -5
echo "---"
git status --short

hr "7. last successful auth method (git config --list filter)"
git config --list | grep -iE "credential|helper|url\." | head -10

echo
echo "=== done ==="
