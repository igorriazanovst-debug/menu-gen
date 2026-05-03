# MG-104d-5d — снять с публикации пустые рецепты-плейсхолдеры
#
# Критерий "плейсхолдер":
#   povar_raw IS NULL
#   AND ingredients = []  (или NULL/пустая строка)
#   AND (kcal IS NULL OR kcal = 0)
#   AND (servings IS NULL OR servings = 0)
#   AND (source_url IS NULL OR source_url = '')
#   AND legacy_id IS NULL
#   AND is_custom = False
#   AND is_published = True   <- это и снимаем
#
# DRY-RUN: ничего не пишет
# APPLY:   MG104D5D_APPLY=1
#
# Идемпотентность: после APPLY рецепт получает is_published=False,
# и условие is_published=True его больше не выберет.

import os, datetime
from django.db import transaction
from apps.recipes.models import Recipe

APPLY = os.environ.get('MG104D5D_APPLY') == '1'
print(f'=== MG-104d-5d: unpublish empty placeholders ===')
print(f'mode: {"APPLY" if APPLY else "DRY-RUN"}')
print(f'time: {datetime.datetime.now().isoformat()}')

# Базовый набор: 376 без povar_raw
base = Recipe.objects.filter(povar_raw__isnull=True)
print(f'\nbase (povar_raw IS NULL): {base.count()}')

candidates = []
skipped = []

for r in base.only(
    'id', 'title', 'ingredients', 'kcal', 'servings',
    'source_url', 'is_custom', 'is_published', 'legacy_id',
):
    reasons = []

    ing = r.ingredients
    if ing is None:
        pass
    elif isinstance(ing, list) and len(ing) == 0:
        pass
    elif isinstance(ing, str) and ing.strip() == '':
        pass
    else:
        reasons.append(f'ingredients_not_empty({type(ing).__name__})')

    if r.kcal not in (None, 0) and float(r.kcal) > 0:
        reasons.append('kcal>0')
    if r.servings not in (None, 0) and r.servings > 0:
        reasons.append('servings>0')

    src = (getattr(r, 'source_url', '') or '').strip()
    if src:
        reasons.append('has_source_url')

    if getattr(r, 'legacy_id', None):
        reasons.append('has_legacy_id')
    if getattr(r, 'is_custom', False):
        reasons.append('is_custom')

    if not getattr(r, 'is_published', False):
        # уже снят — пропускаем (идемпотентность)
        continue

    if reasons:
        skipped.append((r.id, r.title, reasons))
    else:
        candidates.append(r)

print(f'\ncandidates to unpublish: {len(candidates)}')
print(f'skipped (criteria not matched): {len(skipped)}')

if skipped:
    print('\n--- Skipped (sample, first 10) ---')
    for sid, st, sr in skipped[:10]:
        print(f'  id={sid} reasons={sr} | {(st or "")[:60]}')

print('\n--- Candidates (first 20) ---')
for r in candidates[:20]:
    print(f'  id={r.id:<5} | {(r.title or "")[:70]}')

if APPLY:
    with transaction.atomic():
        ids = [r.id for r in candidates]
        n = Recipe.objects.filter(id__in=ids).update(is_published=False)
    print(f'\n>>> APPLIED: is_published=False set for {n} recipes')

    # верификация
    still_pub = Recipe.objects.filter(
        povar_raw__isnull=True, is_published=True
    ).count()
    print(f'verify: povar_raw IS NULL AND is_published=True = {still_pub}')
else:
    print(f'\n(dry-run) would update {len(candidates)} recipes')
    print('To apply: MG104D5D_APPLY=1')
