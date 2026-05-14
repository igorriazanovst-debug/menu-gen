#!/usr/bin/env bash
set -euo pipefail
if [ -z "${GITHUB_TOKEN:-}" ]; then echo "ERROR: export GITHUB_TOKEN first"; exit 1; fi
cd /opt/menugen
REMOTE_URL="$(git remote get-url origin | sed -E 's|https?://[^@/]+@|https://|')"
OWNER_REPO="$(echo "$REMOTE_URL" | sed -E 's|^.*github\.com[:/]||; s|\.git$||')"
SHA="$(git rev-parse HEAD)"
SHORT="$(git rev-parse --short HEAD)"
API="https://api.github.com/repos/${OWNER_REPO}"
AUTH=(-H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json")
echo "repo: ${OWNER_REPO}"
echo "head: ${SHA} (${SHORT})"
echo
echo "=== Recent runs (latest 15) ==="
curl -fsS "${AUTH[@]}" "${API}/actions/runs?per_page=15" \
  | jq -r '.workflow_runs[] | "  id=\(.id)  display=#\(.run_number)  name=\"\(.name | .[0:60])\"  workflow=\(.path | sub(".*/"; ""))  sha=\(.head_sha[0:7])  status=\(.status)  conclusion=\(.conclusion // "running")  url=\(.html_url)"'
echo
echo "=== Runs on HEAD ${SHORT} ==="
RUNS_ON_HEAD="$(curl -fsS "${AUTH[@]}" "${API}/actions/runs?head_sha=${SHA}&per_page=20")"
echo "$RUNS_ON_HEAD" | jq -r '.workflow_runs[] | "  id=\(.id)  display=#\(.run_number)  workflow=\(.path | sub(".*/"; ""))  conclusion=\(.conclusion // "running")  url=\(.html_url)"'
if [ "${1:-}" != "fetch" ]; then echo; echo "To fetch failed logs, re-run with 'fetch' arg."; exit 0; fi
echo
echo "=== Fetching failed-job logs for HEAD runs ==="
FAILED_RUN_IDS="$(echo "$RUNS_ON_HEAD" | jq -r '.workflow_runs[] | select(.conclusion != "success" and .conclusion != "skipped" and .conclusion != "neutral" and .conclusion != null) | .id')"
if [ -z "$FAILED_RUN_IDS" ]; then echo "(no failed runs on HEAD)"; exit 0; fi
OUT_DIR="/tmp/ci_logs_$(date +%s)"
mkdir -p "${OUT_DIR}"
echo "logs -> ${OUT_DIR}"
for RUN_ID in $FAILED_RUN_IDS; do
  echo
  echo "--- RUN ${RUN_ID} ---"
  curl -fsS "${AUTH[@]}" "${API}/actions/runs/${RUN_ID}" | jq -r '"name=\(.name)\nworkflow=\(.path)\nhtml_url=\(.html_url)"'
  echo
  echo "jobs:"
  JOBS_JSON="$(curl -fsS "${AUTH[@]}" "${API}/actions/runs/${RUN_ID}/jobs?per_page=100")"
  echo "$JOBS_JSON" | jq -r '.jobs[] | "  id=\(.id)  name=\"\(.name)\"  conclusion=\(.conclusion)"'
  FAILED_JOBS="$(echo "$JOBS_JSON" | jq -r '.jobs[] | select(.conclusion != "success" and .conclusion != "skipped") | .id')"
  for JOB_ID in $FAILED_JOBS; do
    LOG_FILE="${OUT_DIR}/run-${RUN_ID}-job-${JOB_ID}.log"
    echo
    echo ">>> log for failed job ${JOB_ID}"
    curl -fsSL "${AUTH[@]}" -H "Accept: application/vnd.github.v3.raw" "${API}/actions/jobs/${JOB_ID}/logs" -o "${LOG_FILE}"
    echo "    saved: ${LOG_FILE}  ($(wc -l < "${LOG_FILE}") lines)"
    echo "    last 250 lines:"
    tail -250 "${LOG_FILE}" | sed 's/^/      /'
  done
done
echo
echo ">>> done. all logs: ${OUT_DIR}"
