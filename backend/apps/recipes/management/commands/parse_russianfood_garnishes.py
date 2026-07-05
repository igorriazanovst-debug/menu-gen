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

import logging
import random
import re
import time
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
    retry_waits = [15, 45, 90]
    for attempt, wait in enumerate([0] + retry_waits):
        if wait:
            logger.warning("Пауза %ds перед повтором (попытка %d): %s", wait, attempt + 1, url)
            time.sleep(wait)
        try:
            resp = SESSION.get(url, timeout=15)
            if resp.status_code in (403, 429):
                logger.warning("HTTP %s: %s", resp.status_code, url)
                continue
            if resp.status_code != 200:
                logger.warning("HTTP %s: %s", resp.status_code, url)
                return None
            # случайная пауза delay ± 50%
            time.sleep(delay * (0.5 + random.random()))
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

    # russianfood.com: /recipes/recipe.php?rid=XXXXX
    seen = set()
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "recipe.php" in href and "rid=" in href:
            full = href if href.startswith("http") else BASE_URL + href
            if full not in seen:
                seen.add(full)
                links.append(full)

    # следующая страница: «Следующая →» или цифра page=N
    next_url = None
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if "Следующая" in text or text == "→":
            href = a["href"]
            if "page=" in href:
                # убираем якорь #rcp_list
                next_url = (BASE_URL + href).split("#")[0]
                break

    return links, next_url


# ── recipe page parser ────────────────────────────────────────────────────────


def parse_recipe_page(url: str, delay: float) -> dict | None:
    soup = _get(url, delay)
    if not soup:
        return None

    data: dict = {"source_url": url}

    # ── title ──
    h1 = soup.find("h1")
    if not h1:
        logger.warning("Нет заголовка: %s", url)
        return None
    data["title"] = h1.get_text(strip=True)

    # ── image: og:image ──
    og_img = soup.select_one("meta[property='og:image']")
    if og_img:
        src = og_img.get("content", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            elif not src.startswith("http"):
                src = BASE_URL + src
            data["image_url"] = src

    # ── cook_time и servings из HTML-комментария ──
    # <!-- ... время приготовления 40 мин., затраты времени 15 мин., на 3 порций" -->
    raw_html = str(soup)
    comment_m = re.search(r"время приготовления\s+(\d+)\s*мин.*?на\s+(\d+)\s*пор", raw_html, re.I)
    if comment_m:
        total_min = int(comment_m.group(1))
        data["cook_time_min"] = total_min
        data["cook_time"] = f"{total_min} мин."
        data["servings"] = int(comment_m.group(2))

    # ── ingredients: из <meta name="description"> после «состав:» ──
    desc_meta = soup.select_one("meta[name='description']")
    if desc_meta:
        desc = desc_meta.get("content", "")
        # «Рецепт ..., cостав: ингр1 (кол), ингр2, ...»
        m = re.search(r"[сc]остав\s*:\s*(.+)", desc, re.I)
        if m:
            raw_ingr = m.group(1).strip()
            # разбиваем по запятой, но не внутри скобок
            parts = re.split(r",\s*(?![^(]*\))", raw_ingr)
            for part in parts:
                part = part.strip().rstrip(".")
                if part and len(part) > 1:
                    data.setdefault("ingredients", []).append({"raw": part})

    # ── steps: div.step_n ──
    step_els = soup.select("div.step_n")
    if step_els:
        steps = []
        for el in step_els:
            text = el.get_text(strip=True)
            if text:
                steps.append(text)
        if steps:
            data["steps"] = [{"text": s, "step": i + 1} for i, s in enumerate(steps)]

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
            existing_urls = set(Recipe.objects.filter(source_url__isnull=False).values_list("source_url", flat=True))
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
                self.stdout.write("    FAIL (нет данных)")
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
        "рис",
        "гречк",
        "пшен",
        "булгур",
        "кускус",
        "макарон",
        "паст",
        "спагетти",
        "лапш",
        "перловк",
        "овсян",
        "чечевиц",
        "горох",
        "фасол",
        "нут",
        "полент",
        "ячмен",
        "пшениц",
        "киноа",
        "кукуруз",
    )
    veg_kw = (
        "картофел",
        "картошк",
        "капуст",
        "цветная",
        "брокколи",
        "морков",
        "свекл",
        "тыкв",
        "кабачк",
        "баклажан",
        "цуккин",
        "помидор",
        "томат",
        "огурц",
        "перец",
        "шпинат",
        "спаржа",
        "артишок",
        "фенхель",
        "сельдер",
        "репа",
        "пастернак",
        "батат",
        "авокадо",
        "грибы",
        "гриб",
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
        "title",
        "source_url",
        "image_url",
        "cook_time",
        "cook_time_min",
        "servings",
        "ingredients",
        "steps",
        "nutrition",
        "categories",
        "dish_type",
        "food_group",
        "is_published",
        "is_custom",
        "source",
        "kcal_per_100g",
        "proteins_per_100g",
        "fats_per_100g",
        "carbs_per_100g",
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
