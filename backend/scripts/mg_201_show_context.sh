#!/usr/bin/env bash
# MG-201: показать строки с meal_plan_type и meal_plan c контекстом ±2 строки.
# Берёт пути из /tmp/mg201_audit.tsv.

set -euo pipefail
OUT="/tmp/mg201_audit.tsv"

show_for() {
  local field="$1"
  echo
  echo "###################################################################"
  echo "# $field — контекст ±2 строки"
  echo "###################################################################"

  awk -F'\t' -v f="$field" 'NR>1 && $1==f {print $2"\t"$3}' "$OUT" \
    | sort -u \
    | while IFS=$'\t' read -r file line; do
        # пропускаем сам этот скрипт и audit.sh
        case "$file" in
          */mg_201_audit.sh|*/mg_201_show_context.sh) continue ;;
        esac
        echo
        echo "--- $file:$line ---"
        # ±2 строки вокруг найденной
        local start=$((line - 2))
        local end=$((line + 2))
        [[ $start -lt 1 ]] && start=1
        sed -n "${start},${end}p" "$file" 2>/dev/null \
          | awk -v cur="$line" -v start="$start" '
              {
                ln = start + NR - 1
                marker = (ln == cur) ? ">" : " "
                printf "  %s %4d| %s\n", marker, ln, $0
              }'
      done
}

show_for "meal_plan_type"
show_for "meal_plan"
