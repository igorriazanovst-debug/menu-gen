"""
MG-104b: классификатор Recipe.food_group по композиции ингредиентов
+ типу блюда (dish_type).
"""
from __future__ import annotations
import re
from collections import defaultdict
from typing import Optional

from django.core.management.base import BaseCommand
from apps.recipes.models import Recipe


# ── 1. dish_type detection ──────────────────────────────────────────────────

DISH_TYPE_KEYWORDS = {
    "salad":    [r"\bсалат\w*", r"\bвинегрет\w*", r"\bшуб\w*"],
    "soup":     [r"\bсуп\w*", r"\bборщ\w*", r"\bщи\b", r"\bокрошк\w*",
                 r"\bхарчо\b", r"\bсолянк\w*", r"\bухи?\b", r"\bбульон\w*",
                 r"\bлапш[аеуы]\b", r"\bрассольник\w*"],
    "baking":   [r"\bпиро[гж]\w*", r"\bпирожк\w*", r"\bкекс\w*", r"\bторт\w*",
                 r"\bбулоч\w*", r"\bхлеб\w*", r"\bпеченьe?\w*", r"\bкексик\w*",
                 r"\bлепешк\w*", r"\bблин\w*", r"\bолад\w*", r"\bвафл\w*",
                 r"\bштрудел\w*", r"\bкоржик\w*", r"\bбрауни\b"],
    "porridge": [r"\bкаш\w*", r"\bовсянк\w*", r"\bгречк\w*", r"\bперловк\w*",
                 r"\bманн\w*", r"\bризотто\b", r"\bкускус\w*", r"\bбулгур\w*"],
    "omelet":   [r"\bомлет\w*", r"\bяичниц\w*", r"\bскрембл\w*", r"\bфритатт\w*"],
    "drink":    [r"\bкомпот\w*", r"\bмор[сcщ]\w*", r"\bкоктейл\w*", r"\bсмузи\b",
                 r"\bкисел[ьея]\b", r"\bлимонад\w*", r"\bчай\b", r"\bкофе\b",
                 r"\bнапиток\w*", r"\bглинтвейн\w*"],
    "sauce":    [r"\bсоус\w*", r"\bзаправк\w*", r"\bмаринад\w*", r"\bподлив\w*",
                 r"\bкетчуп\w*"],
    "dessert":  [r"\bдесерт\w*", r"\bмусс\b", r"\bжеле\b", r"\bзефир\w*",
                 r"\bпастил\w*", r"\bпудинг\w*", r"\bтирамису\b", r"\bкрем-брюле\b",
                 r"\bпарфе\b", r"\bсорбет\w*", r"\bморожен\w*"],
}

def detect_dish_type(title: str, categories) -> Optional[str]:
    text = (title or "").lower()
    if isinstance(categories, list):
        text += " " + " ".join(str(c).lower() for c in categories)
    for dtype, patterns in DISH_TYPE_KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, text):
                return dtype
    return None


# ── 2. food group keyword dictionary ────────────────────────────────────────

INGREDIENT_GROUPS = {
    "protein_animal": [
        # мясо
        r"говядин", r"телятин", r"свинин", r"баранин", r"ягнят", r"оленин",
        r"крольчат", r"кролик", r"конин",
        # птица
        r"курин", r"куриц", r"цыплён", r"цыплят", r"индейк", r"индюш",
        r"\bутк[аиеу]?\b", r"гус[ья]", r"перепел",
        # фарши/субпродукты/колбасы
        r"фарш", r"печень", r"печёнк", r"печонк", r"язык", r"сердечк",
        r"бекон", r"ветчин", r"колбас", r"сосис", r"карбонад",
        r"шейк[аи]", r"вырезк[аи]", r"филе курин", r"филе индейк",
        r"котлет",
        # рыба
        r"\bрыб[аеыу]\b", r"\bрыбн", r"лосос", r"сёмг", r"\bсемг", r"форел",
        r"скумбри", r"сельд", r"селёдк", r"тунец",
        r"треск[аиоуы]", r"\bхек\b", r"минта", r"судак", r"щук", r"карп",
        r"окун", r"\bсом\b", r"горбуш", r"кет[аиеыу]\b", r"навага",
        r"палтус", r"камбал", r"налим",
        # морепродукты
        r"креветк", r"кальмар", r"мидии", r"\bмид[ия]\b", r"осьминог",
        r"\bкраб", r"гребеш", r"раки\b", r"анчоус", r"икр[аеыу]",
        # яйца
        r"\bяйц[оаемхуы]?\b", r"яичн",
    ],
    "protein_plant": [
        r"тофу\b", r"темпе\b", r"сейтан\b",
        r"чечевиц", r"\bнут\b", r"\bмаш\b", r"\bфасол",
        r"\bсо[ия]\b", r"соев",
        r"\bгорох\b", r"гороховы", r"гороховой",
    ],
    "dairy": [
        r"молок", r"кефир", r"йогурт", r"ряженк", r"простокваш",
        r"сметан", r"сливк", r"творог", r"мацон",
        r"\bсыр[аеомуы]?\b", r"сырн", r"брынз", r"моцарел", r"фет[аиеу]\b",
        r"маскарпоне", r"рикотта", r"пармезан", r"чеддер", r"камамбер",
        r"тильзитер", r"гауд[аеыу]",
    ],
    "grain": [
        r"мук[аеиоуы]\b", r"мучн", r"крахмал",
        r"гречк", r"гречнев",
        r"\bрис[аеомуы]?\b", r"рисов", r"\bбулгур", r"\bкускус",
        r"кинов\w*", r"квино\w*", r"\bпшен[оаеиыу]\b", r"пшённ", r"пшенн",
        r"\bовс[яё]н", r"геркулес", r"толокн",
        r"\bперлов", r"\bячмен", r"ячнев", r"ячмёнк",
        r"\bманка\b", r"манн[аыо][йяе]\b", r"\bманной\b",
        r"\bкукуруз\w* муки?",
        r"макарон", r"спагетт", r"вермишел", r"лапш",
        r"паст[аы]\b",
        r"хлеб", r"батон", r"сухар", r"лаваш", r"лепёшк",
        r"тесто\b", r"теста\b", r"тесту\b", r"тестом\b",
        r"\bкаш[аеиуы]\b",
    ],
    "vegetable": [
        r"картоф", r"картош",
        r"морков", r"свекл", r"свёкл", r"редис", r"редьк", r"репа\b", r"репы\b",
        r"капуст", r"брокколи", r"цветн[аы] капуст",
        r"огур[еёц]", r"помидор", r"томат",
        r"перец\b", r"перц[аеуы]\b", r"болгар",
        r"кабач[оке]", r"патиссон", r"тыкв",
        r"баклажан",
        r"лук\b", r"\bлуков", r"\bлука\b", r"\bлуку\b", r"\bлуком\b",
        r"чеснок",
        r"шпинат", r"щавел", r"укроп", r"петрушк", r"кинз[аеыу]",
        r"базилик", r"руккол", r"салат\b", r"\bсалат[аеуы]?\b",  # лист.салат
        r"сельдере", r"спарж",
        r"горошек", r"кукуруз",  # как овощ-гарнир
        r"шампиньон", r"\bгриб[аоуыехм]?\b", r"\bопят", r"подосинов", r"подберёз",
        r"белые гриб", r"вешенк", r"лисичк",
        r"авокадо",
        r"оливк", r"маслин",
    ],
    "fruit": [
        r"яблок", r"груш[аеиыу]", r"банан",
        r"апельсин", r"мандарин", r"грейпфрут", r"лимон", r"лайм",
        r"клубник", r"земляник", r"малин", r"ежевик", r"черник", r"брусник",
        r"клюкв", r"смородин", r"крыжовник", r"облепих", r"вишн", r"черешн",
        r"абрикос", r"перси[ке]", r"нектарин", r"слив[аыеуо]\b",
        r"вишн", r"айв[аыу]", r"хурм",
        r"ананас", r"манго", r"киви", r"папайя", r"гранат",
        r"виноград",
        r"арбуз", r"дын[яеи]",
        r"изюм", r"кураг", r"чернослив", r"финик", r"инжир",
    ],
    "oil": [
        r"масл[оаеу] растительн", r"растительн[оы]е масл",
        r"масл[оаеу] подсолнечн", r"подсолнечн[оы]е масл",
        r"оливков[оы]е масл", r"масл[оаеу] оливков",
        r"кунжутн[оы]е масл", r"льнян[оы]е масл",
        r"сливочн[оы]е масл", r"масл[оаеу] сливочн",
        r"\bмаргарин\b", r"\bсал[оа]\b", r"\bсмалец\b",
    ],
}

COMPILED = {
    g: [re.compile(p) for p in pats]
    for g, pats in INGREDIENT_GROUPS.items()
}


def match_groups(name: str) -> set[str]:
    """Множество групп, к которым относится один ингредиент."""
    n = (name or "").lower()
    out = set()
    for g, regs in COMPILED.items():
        if any(r.search(n) for r in regs):
            out.add(g)
    return out


# ── 3. weight estimation ────────────────────────────────────────────────────

def to_grams(qty: str, unit: str) -> float:
    """Грубая нормализация в граммы. Неизвестное → 50."""
    q_str = (qty or "").strip().replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", q_str)
    if not m:
        return 50.0
    try:
        q = float(m.group())
    except ValueError:
        return 50.0
    u = (unit or "").lower()
    if "кг" in u:           return q * 1000
    if "грамм" in u or u == "г":  return q
    if "мл" in u or "литр" in u or u == "л":  return q
    if "ст. ложк" in u or "ст.л" in u:  return q * 15
    if "ч. ложк" in u or "ч.л" in u:    return q * 5
    if "стакан" in u:       return q * 240
    if "штук" in u or u == "шт":  return q * 80
    if "зубч" in u:         return q * 5
    if "пучок" in u or "пучк" in u: return q * 30
    return q * 50  # по вкусу/прочее


# ── 4. dish_type → food_group override ──────────────────────────────────────

def resolve_food_group(
    dish_type: Optional[str],
    scores: dict[str, float],
) -> str:
    """
    Выбираем food_group с учётом dish_type.
    """
    # Грубо суммируем protein animal+plant
    sc = defaultdict(float)
    sc["protein"]   = scores.get("protein_animal", 0) + scores.get("protein_plant", 0)
    sc["dairy"]     = scores.get("dairy", 0)
    sc["grain"]     = scores.get("grain", 0)
    sc["vegetable"] = scores.get("vegetable", 0)
    sc["fruit"]     = scores.get("fruit", 0)
    sc["oil"]       = scores.get("oil", 0)

    total = sum(sc.values()) or 1.0
    share = {k: v / total for k, v in sc.items()}

    # ── жёсткие override от типа блюда ──
    if dish_type == "drink":   return "other"
    if dish_type == "sauce":   return "other"
    if dish_type == "soup":    return "other"
    if dish_type == "omelet":  return "protein"
    if dish_type == "porridge":return "grain"

    if dish_type == "salad":
        # салат = vegetable, если белка <40% массы
        if share["protein"] >= 0.40 and sc["protein"] >= 150:
            return "protein"
        return "vegetable"

    if dish_type == "baking":
        # выпечка ≈ зерновое, если нет явного фруктового доминирования
        if share["fruit"] >= 0.50:
            return "fruit"
        if share["grain"] >= 0.20:
            return "grain"
        return "other"

    if dish_type == "dessert":
        if share["fruit"] >= 0.50:
            return "fruit"
        if share["dairy"] >= 0.50:
            return "dairy"
        return "other"

    # ── основное блюдо: выбираем максимум ──
    # Игнорируем oil как «доминирующее» — он редко самостоятельный компонент
    main = sorted(
        [(k, v) for k, v in sc.items() if k != "oil"],
        key=lambda kv: kv[1],
        reverse=True,
    )
    if not main or main[0][1] == 0:
        return "other"
    top, top_v = main[0]
    second_v = main[1][1] if len(main) > 1 else 0
    # требуем явного перевеса
    if top_v >= max(second_v * 1.3, 50):
        return top
    return "other"


# ── 5. Command ──────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "MG-104b: переклассифицировать food_group по композиции ингредиентов"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="ничего не менять, показать только статистику")
        parser.add_argument("--limit", type=int, default=0,
                            help="ограничить кол-во рецептов (для отладки)")
        parser.add_argument("--show-samples", type=int, default=0,
                            help="вывести N примеров изменённых рецептов")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        limit = opts["limit"]
        show = opts["show_samples"]

        qs = Recipe.objects.all().order_by("id")
        if limit:
            qs = qs[:limit]

        stat_old = defaultdict(int)
        stat_new = defaultdict(int)
        stat_dish = defaultdict(int)
        changed = 0
        samples = []

        for r in qs.iterator():
            stat_old[r.food_group or ""] += 1
            dish = detect_dish_type(r.title, r.categories)
            stat_dish[dish or "—"] += 1

            scores = defaultdict(float)
            for ing in (r.ingredients or []):
                if not isinstance(ing, dict):
                    continue
                name = ing.get("name") or ""
                grams = to_grams(str(ing.get("quantity", "")), str(ing.get("unit", "")))
                groups = match_groups(name)
                for g in groups:
                    scores[g] += grams

            new_group = resolve_food_group(dish, scores)
            stat_new[new_group] += 1

            if new_group != (r.food_group or ""):
                changed += 1
                if show and len(samples) < show:
                    samples.append((r.id, r.title, r.food_group, new_group, dish))
                if not dry:
                    Recipe.objects.filter(pk=r.pk).update(food_group=new_group)

        self.stdout.write(self.style.SUCCESS(
            f"\n{'DRY-RUN ' if dry else ''}готово. Обработано: {sum(stat_old.values())}. "
            f"Изменено: {changed}."
        ))
        self.stdout.write("\n— Распределение СТАРОЕ:")
        for k, v in sorted(stat_old.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"    {k or '(none)':12s} {v}")
        self.stdout.write("\n— Распределение НОВОЕ:")
        for k, v in sorted(stat_new.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"    {k:12s} {v}")
        self.stdout.write("\n— Распределение dish_type:")
        for k, v in sorted(stat_dish.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"    {k:12s} {v}")
        if samples:
            self.stdout.write("\n— Примеры изменений:")
            for rid, t, old, new, d in samples:
                self.stdout.write(f"    [{rid}] {old or '(none)'} → {new}  ({d or '-'})  {t}")
