"""
Парсер гарниров с russianfood.com (fid=17).

Запуск:
  python manage.py parse_russianfood_garnishes --dry-run        # только показать, что нашли
  python manage.py parse_russianfood_garnishes --limit 20       # первые 20 рецептов
  python manage.py parse_russianfood_garnishes --apply          # записать в БД

Опции:
  --dry-run     Парсить, но не сохранять (по умолчанию)
  --apply       Реально сохранять в БД
  --limit N     Ограничить кол-во рецептов (0 = без ограничений)
  --pages N     Ограничить кол-во страниц листинга
  --delay F     Пауза между запросами в секундах (по умолч. 1.5)
  --skip-existing  Пропускать рецепты, уже есть source_url в БД
"""

from __future__ import annotations

import re
import time
import logging
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

BASE_URL = "https://www.russianfood.com"
LIST_URL = "https://www.russianfood.com/recipes/bytype/?fid=17"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": "https://www.russianfood.com/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get(url: str, delay: float = 1.5) -> BeautifulSoup | None:
    try:
        resp = SESSION.get(url, timeout=15)
        if resp.status_code != 200:
            logger.warning("HTTP %s: %s", resp.status_code, url)
            return None
        time.sleep(delay)
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.error("Ошибка запроса %s: %s", url, exc)
        return None


def _to_dec(val) -> Decimal | None:
    if val is None:
        return None
    try:
        s = str(val).replace(",", ".").strip()
        return Decimal(s) if s else None
    except InvalidOperation:
        return None


def _parse_int(val) -> int | None:
    if val is None:
        return None
    m = re.search(r"\d+", str(val))
    return int(m.group()) if m else None


# ── list page parser ──────────────────────────────────────────────────────────

def parse_list_page(url: str, delay: float) -> tuple[list[str], str | None]:
    """Возвращает (список url рецептов, url следующей страницы или None)."""
    soup = _get(url, delay)
    if not soup:
        return [], None

    links = []
    # russianfood.com: карточки рецептов — <div class="recipe"> или <a> с /recipes/recipe/
    for a in soup.select("a[href*='/recipes/recipe/']"):
        href = a.get("href", "")
        if href and href not in links:
            full = href if href.startswith("http") else BASE_URL + href
            if full not in links:
                links.append(full)

    # следующая страница
    next_url = None
    next_a = soup.select_one("a.next, a[rel='next'], .pager a:last-child")
    if next_a:
        href = next_a.get("href", "")
        if href and "page" in href:
            next_url = href if href.startswith("http") else BASE_URL + href

    # альтернатива: ищем ссылку «Следующая» / «>»
    if not next_url:
        for a in soup.find_all("a"):
            text = a.get_text(strip=True)
            if text in ("Следующая", "»", ">", "Вперёд"):
                href = a.get("href", "")
                if href:
                    next_url = href if href.startswith("http") else BASE_URL + href
                    break

    return links, next_url


# ── recipe page parser ────────────────────────────────────────────────────────

def parse_recipe_page(url: str, delay: float) -> dict | None:
    soup = _get(url, delay)
    if not soup:
        return None

    data: dict = {"source_url": url}

    # ── title ──
    title_el = (
        soup.select_one("h1.recipe-title")
        or soup.select_one("h1[itemprop='name']")
        or soup.select_one("h1")
    )
    if not title_el:
        logger.warning("Нет заголовка: %s", url)
        return None
    data["title"] = title_el.get_text(strip=True)

    # ── image ──
    img = (
        soup.select_one("img[itemprop='image']")
        or soup.select_one(".recipe-photo img")
        or soup.select_one(".photo img")
    )
    if img:
        src = img.get("src") or img.get("data-src") or ""
        if src:
            data["image_url"] = src if src.startswith("http") else BASE_URL + src

    # ── cook_time ──
    time_el = (
        soup.select_one("[itemprop='totalTime']")
        or soup.select_one("[itemprop='cookTime']")
        or soup.select_one(".cook-time")
        or soup.select_one(".time")
    )
    if time_el:
        t_str = time_el.get("content") or time_el.get_text(strip=True)
        # PT1H30M → «1 ч 30 мин»
        if t_str and t_str.startswith("PT"):
            h = re.search(r"(\d+)H", t_str)
            m = re.search(r"(\d+)M", t_str)
            parts = []
            if h:
                parts.append(f"{h.group(1)} ч")
            if m:
                parts.append(f"{m.group(1)} мин")
            data["cook_time"] = " ".join(parts) if parts else t_str
            total = (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)
            if total:
                data["cook_time_min"] = total
        else:
            data["cook_time"] = t_str

    # ── servings ──
    srv_el = (
        soup.select_one("[itemprop='recipeYield']")
        or soup.select_one(".servings")
        or soup.select_one(".portions")
    )
    if srv_el:
        srv_text = srv_el.get("content") or srv_el.get_text(strip=True)
        n = _parse_int(srv_text)
        if n:
            data["servings"] = n

    # ── nutrition (microdata) ──
    kcal_el = soup.select_one("[itemprop='calories']")
    prot_el = soup.select_one("[itemprop='proteinContent']")
    fat_el = soup.select_one("[itemprop='fatContent']")
    carb_el = soup.select_one("[itemprop='carbohydrateContent']")

    def _nutr_val(el):
        if not el:
            return None
        c = el.get("content") or el.get_text(strip=True)
        # «150 ккал» → «150»
        m = re.search(r"[\d.,]+", str(c))
        return m.group() if m else None

    kcal = _to_dec(_nutr_val(kcal_el))
    prot = _to_dec(_nutr_val(prot_el))
    fat = _to_dec(_nutr_val(fat_el))
    carb = _to_dec(_nutr_val(carb_el))

    if any(v is not None for v in (kcal, prot, fat, carb)):
        data["kcal_per_100g"] = kcal
        data["proteins_per_100g"] = prot
        data["fats_per_100g"] = fat
        data["carbs_per_100g"] = carb
        # nutrition JSONField (legacy)
        data["nutrition"] = {
            "calories": {"value": str(kcal or ""), "unit": "kcal"},
            "proteins": {"value": str(prot or ""), "unit": "g"},
            "fats": {"value": str(fat or ""), "unit": "g"},
            "carbs": {"value": str(carb or ""), "unit": "g"},
        }

    # ── ingredients ──
    ingredients = []
    # вариант 1: microdata
    for ing_el in soup.select("[itemprop='recipeIngredient'], [itemprop='ingredients']"):
        text = ing_el.get_text(strip=True)
        if text:
            ingredients.append({"raw": text})

    # вариант 2: список внутри .ingredients-list / #ingredients
    if not ingredients:
        for sel in (".ingredients li", "#ingredients li", ".ingr li", ".recipe-ingr li"):
            items = soup.select(sel)
            if items:
                for li in items:
                    text = li.get_text(strip=True)
                    if text:
                        ingredients.append({"raw": text})
                break

    # вариант 3: любые li внутри блока с «ингредиент» в id/class
    if not ingredients:
        for tag in soup.find_all(["ul", "ol"]):
            attr = " ".join([
                tag.get("id") or "",
                " ".join(tag.get("class") or [])
            ]).lower()
            if any(kw in attr for kw in ("ingr", "ingredient", "состав")):
                for li in tag.find_all("li"):
                    text = li.get_text(strip=True)
                    if text:
                        ingredients.append({"raw": text})
                break

    if ingredients:
        data["ingredients"] = ingredients

    # ── steps ──
    steps = []
    # microdata
    for step_el in soup.select("[itemprop='recipeInstructions'] [itemprop='text'], [itemprop='recipeInstructions']"):
        text = step_el.get_text(strip=True)
        if text and text not in steps:
            steps.append(text)

    if not steps:
        # числовые шаги .step / .instruction / .directions li
        for sel in (".step", ".instruction", ".directions li", ".recipe-step", ".cooking-step"):
            items = soup.select(sel)
            if items:
                for el in items:
                    text = el.get_text(strip=True)
                    if text:
                        steps.append(text)
                break

    if steps:
        data["steps"] = [{"text": s, "step": i + 1} for i, s in enumerate(steps)]

    # ── portion_g (попробуем вытащить из заголовка порции) ──
    for tag in soup.find_all(text=re.compile(r"\d+\s*г(?:р)?\.?")):
        m = re.search(r"(\d+)\s*г", str(tag))
        if m:
            g = int(m.group(1))
            if 50 <= g <= 1000:
                data.setdefault("portion_g", g)
                break

    return data


# ── management command ────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Парсит гарниры с russianfood.com и импортирует в БД"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--pages", type=int, default=0)
        parser.add_argument("--delay", type=float, default=1.5)
        parser.add_argument("--skip-existing", action="store_true", default=True)

    def handle(self, *args, **options):
        from apps.recipes.models import Recipe

        apply = options["apply"]
        dry_run = not apply
        limit = options["limit"]
        max_pages = options["pages"]
        delay = options["delay"]
        skip_existing = options["skip_existing"]

        mode = "DRY-RUN" if dry_run else "APPLY"
        self.stdout.write(f"[parse_russianfood_garnishes] mode={mode} limit={limit} pages={max_pages} delay={delay}s")

        # ── собрать все URL рецептов ──
        all_urls: list[str] = []
        page_url = LIST_URL
        page_num = 0

        while page_url:
            page_num += 1
            self.stdout.write(f"  Листинг стр.{page_num}: {page_url}")
            urls, next_url = parse_list_page(page_url, delay)
            self.stdout.write(f"    → найдено {len(urls)} ссылок")

            for u in urls:
                if u not in all_urls:
                    all_urls.append(u)

            if limit and len(all_urls) >= limit:
                all_urls = all_urls[:limit]
                break

            if max_pages and page_num >= max_pages:
                break

            page_url = next_url

        self.stdout.write(f"\nВсего URL рецептов: {len(all_urls)}")

        if not all_urls:
            self.stderr.write("Не нашли ни одного рецепта. Проверьте структуру страницы.")
            return

        # ── проверить уже существующие ──
        existing_urls: set[str] = set()
        if skip_existing:
            existing_urls = set(
                Recipe.objects.filter(source_url__isnull=False)
                .values_list("source_url", flat=True)
            )
            self.stdout.write(f"Уже в БД (по source_url): {len(existing_urls)}")

        # ── парсить каждый рецепт ──
        parsed_ok = 0
        saved = 0
        skipped = 0
        failed = 0

        t0 = time.time()

        for i, url in enumerate(all_urls, 1):
            if url in existing_urls:
                self.stdout.write(f"  [{i}/{len(all_urls)}] SKIP (уже есть): {url}")
                skipped += 1
                continue

            self.stdout.write(f"  [{i}/{len(all_urls)}] Парсим: {url}")
            data = parse_recipe_page(url, delay)

            if not data or not data.get("title"):
                self.stdout.write(f"    FAIL (нет данных)")
                failed += 1
                continue

            parsed_ok += 1

            # обязательные поля для генератора
            data["dish_type"] = "side"
            data["food_group"] = _guess_food_group(data.get("title", ""), data.get("ingredients", []))
            data["is_published"] = True
            data["source"] = "parsed"

            self.stdout.write(
                f"    OK: «{data['title']}» | "
                f"ингр={len(data.get('ingredients', []))} | "
                f"шаги={len(data.get('steps', []))} | "
                f"ккал/100г={data.get('kcal_per_100g', '?')} | "
                f"food_group={data['food_group']}"
            )

            if not dry_run:
                try:
                    with transaction.atomic():
                        recipe = _save_recipe(data)
                        saved += 1
                        self.stdout.write(f"    SAVED id={recipe.pk}")
                except Exception as exc:
                    logger.error("Ошибка сохранения %s: %s", url, exc)
                    failed += 1

        elapsed = time.time() - t0
        self.stdout.write(
            f"\n{'='*60}\n"
            f"Итог [{mode}] за {elapsed:.0f}с:\n"
            f"  Найдено URL:    {len(all_urls)}\n"
            f"  Пропущено:      {skipped}\n"
            f"  Успешно парсим: {parsed_ok}\n"
            f"  Сохранено:      {saved}\n"
            f"  Ошибок:         {failed}\n"
        )

        if dry_run:
            self.stdout.write("Режим DRY-RUN: данные не сохранены. Запустите с --apply для записи.")


# ── helpers ───────────────────────────────────────────────────────────────────

def _guess_food_group(title: str, ingredients: list) -> str:
    """Эвристика: определяем food_group по названию."""
    t = title.lower()
    # крупы/макароны/бобовые → grain
    grain_kw = (
        "рис", "гречк", "пшен", "булгур", "кускус", "макарон", "паст", "спагетти",
        "лапш", "перловк", "овсян", "чечевиц", "горох", "фасол", "нут", "полент",
        "ячмен", "пшениц", "киноа", "кукуруз"
    )
    veg_kw = (
        "картофел", "картошк", "капуст", "цветная", "брокколи", "морков",
        "свекл", "тыкв", "кабачк", "баклажан", "цуккин", "помидор", "томат",
        "огурц", "перец", "шпинат", "спаржа", "артишок", "фенхель", "сельдер",
        "репа", "пастернак", "батат", "авокадо", "грибы", "гриб"
    )
    for kw in grain_kw:
        if kw in t:
            return "grain"
    for kw in veg_kw:
        if kw in t:
            return "vegetable"
    return "grain"  # по умолчанию для гарниров


def _save_recipe(data: dict):
    from apps.recipes.models import Recipe

    fields = {
        "title", "source_url", "image_url", "cook_time", "cook_time_min",
        "servings", "ingredients", "steps", "nutrition", "categories",
        "dish_type", "food_group", "is_published", "is_custom", "source",
        "kcal_per_100g", "proteins_per_100g", "fats_per_100g", "carbs_per_100g",
        "portion_g",
    }
    kwargs = {k: v for k, v in data.items() if k in fields and v is not None}
    kwargs.setdefault("is_custom", False)
    kwargs.setdefault("categories", [])
    kwargs.setdefault("ingredients", [])
    kwargs.setdefault("steps", [])
    kwargs.setdefault("nutrition", {})

    recipe = Recipe(**kwargs)
    recipe.save()
    return recipe
