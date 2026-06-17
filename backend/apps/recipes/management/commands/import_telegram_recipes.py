"""
Импорт рецептов из экспорта Telegram-канала (Telegram Desktop → Export chat → JSON).

Канал tati_cooks: пост = текст с порциями, ингредиентами в граммах, шагами и КБЖУ.
Команда вытаскивает только «полноценные» рецепты (порции + ≥2 ингр. в граммах + КБЖУ),
классифицирует dish_type по хэштегам/ключевым словам, парсит КБЖУ (на порцию) и
заливает в БД с source='parsed'.

КБЖУ в канале указан НА ПОРЦИЮ → kcal/proteins/fats/carbs (на порцию),
portion_g = сумма граммовки ингредиентов / число порций,
*_per_100g считаются из этого. nutrition.calories.value заполняется обязательно —
из него берёт калории генератор стратегии 1.

Запуск:
  python manage.py import_telegram_recipes /path/export.json --dry-run
  python manage.py import_telegram_recipes /path/export.json --apply
  python manage.py import_telegram_recipes /path/export.json --types salad,soup --dry-run

После --dry-run рядом создаётся <export>_parsed.json — вычитайте/поправьте title
(заголовки в канале мусорные), затем можно залить тем же файлом через
import_garnishes_json или повторно этой командой с --from-json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# ── эмодзи/мусор для чистки заголовка ────────────────────────────────────────
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF←-⇿⬀-⯿️]+"
)

# ── классификация dish_type ──────────────────────────────────────────────────
# хэштег #tati_cooks_X → dish_type
_TAG_MAP = {
    "завтрак": "breakfast_dish",
    "творог": "breakfast_dish",
    "суп": "soup",
    "десерт": "dessert",
    "горячее": "main",
    "мясо": "main",
    "рыба": "main",
    "морепродукты": "main",
    "печень": "main",
}

# ключевые слова в шапке (приоритетнее тега для salad/soup/breakfast)
_KW = [
    ("salad", r"салат|нисуаз|винегрет|табуле|\bбоул\b|\bпоке\b|окрошк"),
    ("soup", r"\bсуп\b|\bборщ|гаспачо|крем-?суп|похлёбк|\bщи\b|солянк|харчо|том[\s-]?ям|чечевичн\w*\s+суп"),
    ("breakfast_dish", r"овсян|гранол|сырник|омлет|шакшук|\bкаша\b|панкейк|оладь|яичниц|скрэмбл|порридж|запеканк"),
    ("dessert", r"десерт|чизкейк|маффин|\bпеченье|\bмусс\b|конфет|панна\s*котт"),
]


def classify(head: str, tags: list[str]) -> tuple[str, bool]:
    """Возвращает (dish_type, needs_review). head — первые ~300 символов поста."""
    low = head.lower()
    for dish, pat in _KW:
        if re.search(pat, low):
            return dish, False
    for tag in tags:
        if tag in _TAG_MAP:
            return _TAG_MAP[tag], False
    # ничего не сматчилось — считаем основным, но помечаем на ревью
    return "main", True


# ── парсинг полей ────────────────────────────────────────────────────────────
_KBJU_RE = re.compile(
    r"[кК][бБ][жЖ][уУ][^:\d]*:?\s*"
    r"(\d+[.,]?\d*)\s*[/\\]\s*(\d+[.,]?\d*)\s*[/\\]\s*(\d+[.,]?\d*)\s*[/\\]\s*(\d+[.,]?\d*)"
)
_PORT_RE = re.compile(r"на\s+(\d+)\s*порц", re.I)
_GRAM_RE = re.compile(r"^\s*\+?\s*(\d+[.,]?\d*)\s*г\b\s*(.*)$")
_PLUS_RE = re.compile(r"^\s*\+\s*(.+)$")
_STEP_RE = re.compile(r"^\s*\d+[.)]\s+\S")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _clean_name(name: str) -> str:
    # убрать примечание в скобках и хвостовую пунктуацию
    name = re.sub(r"\s*\([^)]*\)", "", name).strip()
    name = name.rstrip(".,;:").strip()
    return name


def parse_recipe(text: str) -> dict | None:
    kb = _KBJU_RE.search(text)
    port = _PORT_RE.search(text)
    if not kb or not port:
        return None

    lines = text.split("\n")
    # индекс строки «На N порций»
    port_idx = next((i for i, l in enumerate(lines) if _PORT_RE.search(l)), None)
    if port_idx is None:
        return None

    servings = int(port.group(1))

    # ── ингредиенты: от «На N порций» до первого шага/КБЖУ ──
    ingredients = []
    total_g = 0.0
    for l in lines[port_idx + 1:]:
        if _STEP_RE.match(l) or _KBJU_RE.search(l) or l.strip().startswith("#"):
            break
        gm = _GRAM_RE.match(l)
        if gm:
            qty = gm.group(1)
            name = _clean_name(gm.group(2))
            if name:
                ingredients.append({"name": name, "quantity": qty, "unit": "г"})
                total_g += _num(qty)
            continue
        pm = _PLUS_RE.match(l)
        if pm:
            name = _clean_name(pm.group(1))
            if name:
                ingredients.append({"name": name, "quantity": "", "unit": ""})
    if len(ingredients) < 2:
        return None

    # ── шаги: нумерованные строки ──
    steps = []
    for l in lines:
        if _STEP_RE.match(l):
            txt = re.sub(r"^\s*\d+[.)]\s+", "", l).strip()
            if txt:
                steps.append({"step": len(steps) + 1, "text": txt})

    # ── КБЖУ (на порцию) ──
    kcal, prot, fat, carb = (_num(kb.group(i)) for i in range(1, 5))

    portion_g = round(total_g / servings) if servings else round(total_g)
    nutrition = {
        "calories": {"value": round(kcal, 1), "unit": "ккал"},
        "protein": {"value": round(prot, 1), "unit": "г"},
        "fat": {"value": round(fat, 1), "unit": "г"},
        "carbs": {"value": round(carb, 1), "unit": "г"},
    }

    def per100(x):
        return round(x / portion_g * 100, 1) if portion_g else None

    # ── заголовок (best-effort, требует ревью) ──
    head_lines = [l.strip() for l in lines[:port_idx] if l.strip() and not l.strip().startswith("#")]
    title, title_review = _guess_title(head_lines)

    head = text[:300]
    tags = re.findall(r"#tati_cooks_(\w+)", text)
    dish_type, dt_review = classify(head, tags)

    return {
        "title": title,
        "dish_type": dish_type,
        "servings": servings,
        "portion_g": portion_g,
        "ingredients": ingredients,
        "steps": steps,
        "nutrition": nutrition,
        "kcal": round(kcal, 1),
        "proteins": round(prot, 1),
        "fats": round(fat, 1),
        "carbs": round(carb, 1),
        "kcal_per_100g": per100(kcal),
        "proteins_per_100g": per100(prot),
        "fats_per_100g": per100(fat),
        "carbs_per_100g": per100(carb),
        "serving_size_label": f"1 порция / {portion_g} г",
        "_title_review": bool(title_review),
        "_dishtype_review": bool(dt_review),
        "_needs_review": bool(title_review or dt_review),
        "_tags": tags,
    }


# вступительные/разговорные зачины — такие строки не являются названием блюда
_INTRO_WORDS = (
    r"залить|разлож|нарез|обжар|смеша|добав|варить|приготов|духовк|поэтому|"
    r"если|когда|сегодня|пока|наступа|продолжа|время|кажется|хочется|меня|"
    r"неделя|месяц|друзья|привет|доброго|утренн|очередн|скучаю|февральск|"
    r"конец|восьмичас|любителям|гастроном|классика|песня|встретил|пошел|"
    r"следующ|постновогод|для закреплен|что получится|что может|как насчёт|"
    r"в этой|на завтрак был|на прошлой|суть сохранила"
)


def _guess_title(head_lines: list[str]) -> tuple[str, bool]:
    """Подбираем короткую «именную» строку, ближайшую к «На N порций».
    Заголовки в канале неаккуратные — флаг review=True требует ручной правки."""
    def strip(s: str) -> str:
        return _EMOJI.sub("", s).rstrip(" :").strip()

    cand = []
    for l in head_lines:
        s = strip(l)
        if not s or _GRAM_RE.match(s) or _STEP_RE.match(s):
            continue
        if re.search(r"[.!?…]$", s):  # законченное предложение — скорее вступление
            continue
        if re.search(r"\b(" + _INTRO_WORDS + r")\w*", s, re.I):
            continue
        words = s.split()
        if 1 <= len(words) <= 7:
            cand.append(s)
    if cand:
        return cand[-1], False  # ближайшая к «На N порций» строка — обычно название
    # фолбэк: первые 6 слов первой строки
    if head_lines:
        return " ".join(strip(head_lines[0]).split()[:6]) or "Без названия", True
    return "Без названия", True


def _get_text(m: dict) -> str:
    t = m.get("text")
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        return "".join(p if isinstance(p, str) else p.get("text", "") for p in t)
    return ""


class Command(BaseCommand):
    help = "Импорт рецептов из JSON-экспорта Telegram-канала (порции+граммовка+КБЖУ)"

    def add_arguments(self, parser):
        parser.add_argument("export_file", help="JSON-экспорт Telegram-чата")
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument(
            "--types", default="salad,soup,main,breakfast_dish",
            help="dish_type через запятую (по умолч. salad,soup,main,breakfast_dish)",
        )
        parser.add_argument("--from-json", action="store_true",
                            help="export_file — уже распарсенный _parsed.json (после ручной правки title)")

    def handle(self, *args, **options):
        from apps.recipes.models import Recipe

        path = Path(options["export_file"])
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")

        apply = options["apply"]
        dry_run = options["dry_run"] or not apply
        want_types = {t.strip() for t in options["types"].split(",") if t.strip()}
        from_json = options["from_json"]

        # ── получить список распарсенных рецептов ──
        if from_json:
            recipes = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            msgs = data.get("messages", [])
            recipes = []
            for m in msgs:
                if m.get("type") != "message":
                    continue
                txt = _get_text(m)
                if not txt.strip():
                    continue
                rec = parse_recipe(txt)
                if rec:
                    rec["source_msg_id"] = m.get("id")
                    recipes.append(rec)

        self.stdout.write(f"Распарсено полноценных рецептов: {len(recipes)}")

        # ── фильтр по типам ──
        recipes = [r for r in recipes if r["dish_type"] in want_types]
        self.stdout.write(f"После фильтра по типам {sorted(want_types)}: {len(recipes)}\n")

        # ── сводка по типам ──
        from collections import Counter
        by_type = Counter(r["dish_type"] for r in recipes)
        for dt, c in by_type.most_common():
            self.stdout.write(f"  {dt:<16} {c}")
        self.stdout.write("")

        # ── таблица для ревью ──
        # T! — поправить title, D? — проверить dish_type (угадан по фолбэку)
        self.stdout.write(f"  {'flags':>5} {'тип':<14} {'порц':>4} {'ккал':>5} {'ингр':>4} {'шаги':>4}  title")
        self.stdout.write("  " + "-" * 78)
        n_title = n_dt = 0
        for r in recipes:
            t_flag = "T!" if r.get("_title_review") else "  "
            d_flag = "D?" if r.get("_dishtype_review") else "  "
            n_title += bool(r.get("_title_review"))
            n_dt += bool(r.get("_dishtype_review"))
            self.stdout.write(
                f"  {t_flag}{d_flag:>3} {r['dish_type']:<14} {r['servings']:>4} "
                f"{r['kcal']:>5.0f} {len(r['ingredients']):>4} {len(r['steps']):>4}  {r['title'][:45]}"
            )
        self.stdout.write(f"\n  T! поправить заголовок: {n_title}   D? проверить тип: {n_dt}")

        # ── всегда выгружаем parsed.json для ручной вычитки ──
        if not from_json:
            out = path.with_name(path.stem + "_parsed.json")
            out.write_text(json.dumps(recipes, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"\nВыгружено для ревью: {out}")
            self.stdout.write("Поправьте title (⚠ — обязательно), затем: "
                              f"--from-json {out.name} --apply")

        if dry_run:
            self.stdout.write("\nDRY-RUN. Записи нет. Запустите с --apply.")
            return

        # ── запись в БД ──
        saved = skipped = failed = 0
        existing_titles = set(
            Recipe.objects.filter(source="parsed").values_list("title", flat=True)
        )
        for r in recipes:
            if r["title"] in existing_titles or r["title"] == "Без названия":
                skipped += 1
                continue
            try:
                with transaction.atomic():
                    Recipe.objects.create(
                        title=r["title"],
                        dish_type=r["dish_type"],
                        servings=r["servings"],
                        portion_g=r["portion_g"],
                        ingredients=r["ingredients"],
                        steps=r["steps"],
                        nutrition=r["nutrition"],
                        kcal=r["kcal"],
                        proteins=r["proteins"],
                        fats=r["fats"],
                        carbs=r["carbs"],
                        kcal_per_100g=r["kcal_per_100g"],
                        proteins_per_100g=r["proteins_per_100g"],
                        fats_per_100g=r["fats_per_100g"],
                        carbs_per_100g=r["carbs_per_100g"],
                        serving_size_label=r["serving_size_label"],
                        categories=[],
                        is_published=True,
                        is_custom=False,
                        source="parsed",
                    )
                    saved += 1
                    existing_titles.add(r["title"])
            except Exception as exc:
                self.stderr.write(f"Ошибка «{r['title']}»: {exc}")
                failed += 1

        self.stdout.write(
            f"\n{'='*50}\nИтог [APPLY]:\n"
            f"  Сохранено: {saved}\n  Пропущено: {skipped}\n  Ошибок:    {failed}\n"
        )
        self.stdout.write(
            "\nПосле импорта обновите разметку и проверьте повторы:\n"
            "  python manage.py mg_seed_plate --apply\n"
            "  python manage.py mg_analyze_s1_repeats --runs 20 --days 7"
        )
