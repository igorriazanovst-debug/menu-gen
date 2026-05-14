#!/usr/bin/env bash
# Fetch failed-job logs for given workflow run IDs.
# Usage:
#   export GITHUB_TOKEN=ghp_xxx
#   bash /opt/menugen/backend/scripts/fetch_ci_logs.sh 26 85
set -euo pipefail

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: export GITHUB_TOKEN first (PAT with public_repo or repo scope)"
  exit 1
fi
if [ "$#" -lt 1 ]; then
  echo "Usage: $0 RUN_ID [RUN_ID ...]"
  exit 1
fi

cd /opt/menugen
REMOTE_URL="$(git remote get-url origin | sed -E 's|https?://[^@/]+@|https://|')"
OWNER_REPO="$(echo "$REMOTE_URL" \
    | sed -E 's|^.*github\.com[:/]([^/]+/[^/]+?)(\.git)?$|\1|')"

API="https://api.github.com/repos/${OWNER_REPO}"
AUTH=(-H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json")

OUT_DIR="/tmp/ci_logs_$(date +%s)"
mkdir -p "${OUT_DIR}"
echo "logs → ${OUT_DIR}"
echo

for RUN_ID in "$@"; do
  echo "================================================================"
  echo "  RUN ${RUN_ID}"
  echo "================================================================"

  # 1. run metadata
  curl -fsS "${AUTH[@]}" "${API}/actions/runs/${RUN_ID}" \
    | jq -r '"name=\(.name)\nworkflow=\(.path)\nstatus=\(.status)\nconclusion=\(.conclusion)\nhtml_url=\(.html_url)"'
  echo

  # 2. list jobs, find failed ones
  echo ">>> jobs:"
  curl -fsS "${AUTH[@]}" "${API}/actions/runs/${RUN_ID}/jobs?per_page=100" \
    | jq -r '.jobs[] | "  - id=\(.id)  name=\"\(.name)\"  conclusion=\(.conclusion)  url=\(.html_url)"'

  FAILED_JOB_IDS="$(curl -fsS "${AUTH[@]}" "${API}/actions/runs/${RUN_ID}/jobs?per_page=100" \
      | jq -r '.jobs[] | select(.conclusion != "success" and .conclusion != "skipped") | .id')"

  if [ -z "$FAILED_JOB_IDS" ]; then
    echo "  (no failed jobs)"
    continue
  fi

  for JOB_ID in $FAILED_JOB_IDS; do
    echo
    echo "--- log for failed job ${JOB_ID} ---"
    LOG_FILE="${OUT_DIR}/run-${RUN_ID}-job-${JOB_ID}.log"
    # /logs returns text, not JSON
    curl -fsSL "${AUTH[@]}" -H "Accept: application/vnd.github.v3.raw" \
         "${API}/actions/jobs/${JOB_ID}/logs" -o "${LOG_FILE}"
    echo "  saved: ${LOG_FILE}  ($(wc -l < "${LOG_FILE}") lines)"
    echo "  >>> last 200 lines:"
    tail -200 "${LOG_FILE}" | sed 's/^/    /'
  done
done

echo
echo ">>> all logs in ${OUT_DIR}"
ls -la "${OUT_DIR}"
