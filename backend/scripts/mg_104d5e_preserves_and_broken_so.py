"""
MG-104d-5e: пометить заготовки + переcчитать рецепты с битым servings.

Запуск:
  # DRY-RUN
  docker compose exec backend bash -c 'python manage.py shell < /app/scripts/mg_104d5e_preserves_and_broken_so.py'
  # APPLY
  docker compose exec -e MG104D5E_APPLY=1 backend bash -c \
    'python manage.py shell < /app/scripts/mg_104d5e_preserves_and_broken_so.py'

Что делает:
  1. Помечает заготовки флагом is_preserve=True в povar_raw (по жёсткому regex по title).
  2. Для рецептов с битым servings (so>=50, dw<3000г, не выпечка, не заготовка)
     пересчитывает sn = max(1, round(dw/300)) и kcal/p/f/c.

Идемпотентен.
"""
import os, re, json
from django.db import transaction
from apps.recipes.models import Recipe

APPLY = os.environ.get("MG104D5E_APPLY", "").lower() in ("1","true","yes")
SERVING_G = float(os.environ.get("MG104D5E_SERVING_G", "300"))

# Жёсткий regex для заготовок: title начинается одним из ключевых слов
# или содержит "на зиму". Никаких "квашеной капусты" внутри.
PRESERVE_TITLE_RE = re.compile(
    r'(?:^|\s)('
    r'на\s+зиму'
    r'|тушенк[аи]?'
    r'|тушёнк[аи]?'
    r'|солонина'
    r'|икра\s+(?:из|кабачков|баклажан|свекл|грибн|овощн|морков|сельд)'
    r'|заготовк'
    r'|закатк'
    r'|закрутк'
    r')\b',
    re.IGNORECASE,
)

# Анти-сигнал: если в title есть выпечка/блюдо — это не заготовка
EXCLUDE_RE = re.compile(
    r'(пирог|печенье|пирожн|тарт|кекс|маффин|булочк|круассан|штрудел|рулет|торт|чизкейк|щи|борщ|суп|салат)',
    re.IGNORECASE,
)

# Тип 1: битый so>=50, не выпечка, не заготовка
UNIT_TITLE_RE = re.compile(
    r'(печенье|торт|пирог|пирожн|булочк|маффин|кекс|капкейк|безе|меренг|пахлав|'
    r'тарталет|корзиноч|трюфел|конфет|карамел|зефир|пастил|мармелад|пряник|'
    r'вафл|круассан|эклер|профитрол|макарон|чизкейк|роллет|рулет|бискви|'
    r'кейк-поп|шарик|сердечк|плитк|плиточк|колечк|мороженое|щербет|сорбет|'
    r'мусс|желе|сгущ|глазур|финансье|фадж|помадк|самс|пончик|лепешк|питакия)',
    re.IGNORECASE,
)


def calc_kbju_per_serving(r, sn_new, dw, kbju_acc):
    """Пересчитать kcal/p/f/c на одну порцию через kbju_acc (накопленный по ингредиентам)."""
    if sn_new <= 0:
        return None
    return {
        "kcal":     round(kbju_acc["kcal"]     / sn_new, 2),
        "proteins": round(kbju_acc["proteins"] / sn_new, 2),
        "fats":     round(kbju_acc["fats"]     / sn_new, 2),
        "carbs":    round(kbju_acc["carbs"]    / sn_new, 2),
    }


# ---------- сбор кандидатов ----------
preserves = []
broken_so = []

print(f"[mg-104d-5e] APPLY={APPLY}  SERVING_G={SERVING_G}")

qs = Recipe.objects.filter(povar_raw__mg_104d5b_v=1).only(
    'id','title','servings','servings_normalized','kcal','proteins','fats','carbs','povar_raw'
)
total = qs.count()
print(f"[mg-104d-5e] candidates pool (mg_104d5b_v=1): {total}")

for r in qs:
    pr = r.povar_raw or {}
    dw = pr.get('dish_weight_g_calc') or 0
    try: dw = float(dw)
    except: dw = 0
    title = r.title or ''
    sn = r.servings_normalized or 0
    so = r.servings or 0

    is_preserve = bool(PRESERVE_TITLE_RE.search(title)) and not EXCLUDE_RE.search(title)
    if is_preserve:
        preserves.append(r)
        continue

    # Тип 1: so>=50, не выпечка, не заготовка, dw<3000 (иначе вероятно заготовка/большое блюдо)
    if so >= 50 and dw < 3000 and dw > 0 and not UNIT_TITLE_RE.search(title):
        sn_new = max(1, round(dw / SERVING_G))
        if sn_new != sn:
            broken_so.append((r, sn_new))

print(f"\n=== PRESERVES (will set is_preserve=True): {len(preserves)} ===")
print(f'{"id":>5} {"so":>4} {"sn":>4} {"dw":>7} title')
for r in sorted(preserves, key=lambda x: -(x.servings_normalized or 0)):
    pr = r.povar_raw or {}
    dw = pr.get('dish_weight_g_calc') or 0
    print(f'{r.id:>5} {r.servings or 0:>4} {r.servings_normalized or 0:>4} {dw:>7}  {r.title[:60]}')

print(f"\n=== BROKEN so (will recalc sn): {len(broken_so)} ===")
print(f'{"id":>5} {"so":>4} {"sn":>4} → {"sn_new":>5} {"dw":>7} {"kcal":>6} title')
for r, sn_new in broken_so:
    pr = r.povar_raw or {}
    dw = pr.get('dish_weight_g_calc') or 0
    print(f'{r.id:>5} {r.servings or 0:>4} {r.servings_normalized or 0:>4} → {sn_new:>5} {dw:>7} {r.kcal or 0:>6.1f}  {r.title[:50]}')

# ---------- APPLY ----------
if not APPLY:
    print("\n[mg-104d-5e] DRY-RUN — БД не тронута")
else:
    print(f"\n[mg-104d-5e] APPLYING...")
    n_preserve = 0
    n_broken = 0
    with transaction.atomic():
        # 1. Заготовки: только метка
        for r in preserves:
            pr = r.povar_raw or {}
            if pr.get('is_preserve') is True:
                continue
            pr['is_preserve'] = True
            pr['mg_104d5e_v'] = 1
            r.povar_raw = pr
            r.save(update_fields=['povar_raw'])
            n_preserve += 1

        # 2. Битые so: пересчёт sn + kcal/p/f/c (масштабом old_sn/new_sn)
        for r, sn_new in broken_so:
            sn_old = r.servings_normalized or 0
            if sn_old == sn_new:
                continue
            pr = r.povar_raw or {}
            pr['servings_normalized_pre5e'] = sn_old
            pr['kcal_pre5e'] = float(r.kcal or 0)
            pr['mg_104d5e_v'] = 1
            # Пересчёт kcal/p/f/c: total = sn_old * old_per_serving, new_per_serving = total / sn_new
            if sn_old > 0:
                scale = sn_old / sn_new
                r.kcal     = round(float(r.kcal or 0) * scale, 2)
                r.proteins = round(float(r.proteins or 0) * scale, 2)
                r.fats     = round(float(r.fats or 0) * scale, 2)
                r.carbs    = round(float(r.carbs or 0) * scale, 2)
            r.servings_normalized = sn_new
            r.povar_raw = pr
            r.save(update_fields=['servings_normalized','kcal','proteins','fats','carbs','povar_raw'])
            n_broken += 1

    print(f"[mg-104d-5e] applied: preserves={n_preserve}, broken_so_recalc={n_broken}")

print("\n[mg-104d-5e] done.")
