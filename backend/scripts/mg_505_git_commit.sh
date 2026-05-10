#!/bin/bash
# MG_505_V_git_commit
set -e
cd /opt/menugen

echo "=== git status ==="
git status -s

echo
echo "=== diff stats ==="
git diff --stat

echo
echo "=== add ==="
git add -A
git status -s

echo
echo "=== commit ==="
git commit -m "MG-504/505: cheat-meal — поля Profile + слот в меню

MG-504: Profile fields bedtime_hour, cheat_meal_interval, last_cheat_meal_date
  + миграция 0005_mg_504_profile_cheat_meal
  + ProfileSerializer/ProfileUpdateSerializer (users + family)
  + types.ts UserProfile

MG-505: cheat-meal slot
  + MenuItem.is_cheat_meal + миграция 0008_menuitem_is_cheat_meal
  + generator: helpers _mg505_is_cheat_day/_pick_cheat_slot/_mark_cheat_meal_used
  + _pick_for_role(is_cheat=True) — bypass MG-302/303/502/503 для protein
  + views.py: bulk_create + апдейт last_cheat_meal_date после генерации
  + types.ts MenuItem.is_cheat_meal

Tests: 128 passed (29 users + 13 family + 86 menu)"

echo
echo "=== push ==="
git push
