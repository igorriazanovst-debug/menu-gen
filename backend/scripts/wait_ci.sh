#!/usr/bin/env bash
# Poll GitHub Actions for flutter_ci on the current HEAD.
# Requires: curl, jq, and env var GITHUB_TOKEN (read-only is fine for public repos
# too — but rate-limited if unset). NEVER hardcodes the token.
#
# Usage:
#   export GITHUB_TOKEN=ghp_xxx   # personal access token, scope: repo or public_repo
#   bash /opt/menugen/backend/scripts/wait_ci.sh
#
# Reads owner/repo from `git remote get-url origin`.
set -euo pipefail

cd /opt/menugen

REMOTE_URL="$(git remote get-url origin)"
# Strip credentials if present in URL (e.g. https://user:token@github.com/...)
REMOTE_URL="$(echo "$REMOTE_URL" | sed -E 's|https?://[^@/]+@|https://|')"

# Parse owner/repo from URL (supports https://github.com/OWNER/REPO[.git] and git@github.com:OWNER/REPO[.git])
OWNER_REPO="$(echo "$REMOTE_URL" \
    | sed -E 's|^.*github\.com[:/]([^/]+/[^/]+?)(\.git)?$|\1|')"

SHA="$(git rev-parse HEAD)"
SHORT="$(git rev-parse --short HEAD)"

echo "repo: ${OWNER_REPO}"
echo "head: ${SHA} (${SHORT})"
echo

AUTH=()
if [ -n "${GITHUB_TOKEN:-}" ]; then
  AUTH=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
fi

API="https://api.github.com/repos/${OWNER_REPO}/actions/runs?head_sha=${SHA}&per_page=20"

i=0
MAX=60     # ~ 60 * 15s = 15 min ceiling
SLEEP=15

while : ; do
  i=$((i+1))
  RESP="$(curl -fsS "${AUTH[@]}" -H "Accept: application/vnd.github+json" "$API" || true)"
  if [ -z "$RESP" ]; then
    echo "[$i] empty response from GitHub API; retrying in ${SLEEP}s"
    sleep "$SLEEP"; continue
  fi

  # Summary of all runs on this SHA
  echo "[$i] runs on ${SHORT}:"
  echo "$RESP" | jq -r '
    .workflow_runs[]
    | "  - " + .name
      + "  status=" + .status
      + "  conclusion=" + (.conclusion // "running")
      + "  url=" + .html_url
  ' 2>/dev/null || { echo "  (couldn't parse — raw below)"; echo "$RESP" | head -30; }

  # Are there any runs still in non-terminal state?
  PENDING="$(echo "$RESP" | jq -r '[.workflow_runs[] | select(.status != "completed")] | length')"
  TOTAL="$(echo "$RESP" | jq -r '.workflow_runs | length')"

  if [ "$TOTAL" = "0" ]; then
    echo "[$i] no runs registered yet on this SHA (CI may not have started); retrying"
  elif [ "$PENDING" = "0" ]; then
    echo
    echo ">>> all runs completed."
    echo "$RESP" | jq -r '.workflow_runs[] | "\(.name): \(.conclusion)  \(.html_url)"'

    # exit non-zero if anything failed
    FAILED="$(echo "$RESP" | jq -r '[.workflow_runs[] | select(.conclusion != "success" and .conclusion != "skipped" and .conclusion != "neutral")] | length')"
    if [ "$FAILED" != "0" ]; then
      echo
      echo "!!! ${FAILED} run(s) did NOT succeed."
      # Print failed jobs summary
      echo "$RESP" | jq -r '.workflow_runs[] | select(.conclusion != "success" and .conclusion != "skipped" and .conclusion != "neutral") | .id' \
        | while read -r RID; do
            echo
            echo "--- failed run $RID — jobs ---"
            curl -fsS "${AUTH[@]}" -H "Accept: application/vnd.github+json" \
                 "https://api.github.com/repos/${OWNER_REPO}/actions/runs/$RID/jobs" \
              | jq -r '.jobs[] | "  job: \(.name)  conclusion=\(.conclusion)  url=\(.html_url)"'
          done
      exit 1
    fi
    exit 0
  fi

  if [ "$i" -ge "$MAX" ]; then
    echo "timeout after ${MAX} polls (~$((MAX*SLEEP/60)) min)"; exit 2
  fi
  sleep "$SLEEP"
done
