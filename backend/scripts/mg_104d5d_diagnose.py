# MG-104d-5d — диагностика 376 рецептов без povar_raw (v2)
# Запуск:
#   docker compose -f /opt/menugen/docker-compose.yml exec -T backend bash -c \
#     'python manage.py shell < /app/scripts/mg_104d5d_diagnose.py'

from apps.recipes.models import Recipe
from collections import Counter

OUT = '/tmp/mg104d5d_diag.tsv'

qs = Recipe.objects.filter(povar_raw__isnull=True)
total = qs.count()
print(f'recipes with povar_raw IS NULL: {total}')

fields = set(f.name for f in Recipe._meta.get_fields() if not f.is_relation)
print(f'\nRecipe fields: {sorted(fields)}')

ing_null = 0
ing_empty = 0
ing_list = 0
ing_str = 0
ing_other = 0
has_kcal = 0
has_servings = 0
has_legacy = 0
is_custom_yes = 0
is_published_yes = 0
sources = Counter()

rows = []

for r in qs.only(
    'id', 'title', 'ingredients', 'kcal', 'servings',
    'source_url', 'is_custom', 'is_published', 'legacy_id', 'author_id',
):
    ing = r.ingredients
    if ing is None:
        ing_state = 'NULL'; ing_null += 1
    elif isinstance(ing, list):
        if len(ing) == 0:
            ing_state = 'EMPTY_LIST'; ing_empty += 1
        else:
            ing_state = f'LIST({len(ing)})'; ing_list += 1
    elif isinstance(ing, str):
        if ing.strip() == '':
            ing_state = 'EMPTY_STR'; ing_empty += 1
        else:
            ing_state = f'STR({len(ing)})'; ing_str += 1
    else:
        ing_state = f'OTHER({type(ing).__name__})'; ing_other += 1

    kcal = float(r.kcal) if r.kcal else 0
    sn = r.servings or 0
    if kcal > 0: has_kcal += 1
    if sn > 0: has_servings += 1

    src = getattr(r, 'source_url', '') or ''
    if src:
        try:
            dom = src.split('/')[2] if '://' in src else src.split('/')[0]
            sources[dom] += 1
        except Exception:
            sources['_parse_err'] += 1
    else:
        sources['_no_url'] += 1

    if getattr(r, 'legacy_id', None):
        has_legacy += 1
    if getattr(r, 'is_custom', False):
        is_custom_yes += 1
    if getattr(r, 'is_published', False):
        is_published_yes += 1

    rows.append((
        r.id, (r.title or '')[:80], ing_state, kcal, sn,
        bool(getattr(r, 'is_custom', False)),
        bool(getattr(r, 'is_published', False)),
        getattr(r, 'legacy_id', '') or '',
        getattr(r, 'author_id', '') or '',
        src,
    ))

print(f'\n=== Состояние ingredients ===')
print(f'  NULL:        {ing_null}')
print(f'  EMPTY:       {ing_empty}')
print(f'  LIST:        {ing_list}')
print(f'  STR:         {ing_str}')
print(f'  OTHER:       {ing_other}')

print(f'\n=== Прочие поля ===')
print(f'  kcal>0:           {has_kcal}')
print(f'  servings>0:       {has_servings}')
print(f'  is_custom=True:   {is_custom_yes}')
print(f'  is_published=T:   {is_published_yes}')
print(f'  legacy_id есть:   {has_legacy}')

print(f'\n=== Источники (домены) ===')
for dom, n in sources.most_common(20):
    print(f'  {n:>4}  {dom}')

print(f'\n=== Примеры (первые 30) ===')
for row in rows[:30]:
    print(f'  id={row[0]:<5} ing={row[2]:<14} kcal={row[3]:<7} sn={row[4]:<3} '
          f'custom={int(row[5])} pub={int(row[6])} legacy={str(row[7]):<6} | {row[1]}')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('id\ttitle\tingredients_state\tkcal\tservings\tis_custom\tis_published\tlegacy_id\tauthor_id\tsource_url\n')
    for row in rows:
        f.write('\t'.join(str(x).replace('\t', ' ').replace('\n', ' ') for x in row) + '\n')
print(f'\nFull dump: {OUT} ({len(rows)} rows)')
