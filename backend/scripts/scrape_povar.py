"""
Scraper for povar.ru — collects recipes by cuisine for Italian, French,
and Eastern European (Russian, Ukrainian, Polish) cuisines.

Parsing is based on Schema.org microdata (itemprop attributes) that
povar.ru embeds in every recipe page — much more reliable than CSS classes.

Usage:
    python scrape_povar.py [--pages N] [--output path/to/output.json]

Output: JSON array of raw recipe dicts → scripts/scraped_recipes.json
"""
import argparse
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://povar.ru"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Per-cuisine config: list slug, DB country name, pages to scrape
CUISINE_CONFIG = {
    "Italian":   {"slug": "/list/italyanskaya/",  "country": "Италия",   "pages": 4},
    "French":    {"slug": "/list/francuzskaya/",  "country": "Франция",  "pages": 4},
    "Russian":   {"slug": "/list/russkaya/",      "country": "Россия",   "pages": 3},
    "Ukrainian": {"slug": "/list/ukrainskaya/",   "country": "Украина",  "pages": 3},
    "Polish":    {"slug": "/list/polskaya/",      "country": "Польша",   "pages": 2},
}

MEAL_TYPE_MAP = {
    "на завтрак": "breakfast",
    "завтрак":    "breakfast",
    "на обед":    "lunch",
    "обед":       "lunch",
    "на ужин":    "dinner",
    "ужин":       "dinner",
    "на перекус": "snack",
    "перекус":    "snack",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch(url: str, delay: float = 0.8) -> Optional[BeautifulSoup]:
    time.sleep(delay)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# List page: collect recipe URLs
# ---------------------------------------------------------------------------

def collect_recipe_urls(slug: str, pages: int) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    recipe_pattern = re.compile(r"^/recipes/.+\.html$")

    for page in range(1, pages + 1):
        page_url = BASE_URL + slug if page == 1 else f"{BASE_URL}{slug}{page}/"
        soup = fetch(page_url)
        if not soup:
            continue
        for a in soup.find_all("a", href=recipe_pattern):
            full = BASE_URL + a["href"]
            if full not in seen:
                seen.add(full)
                urls.append(full)
        logger.info("List page %d/%d → %d URLs so far", page, pages, len(urls))

    return urls


# ---------------------------------------------------------------------------
# Detail page parsers — all based on Schema.org itemprop microdata
# ---------------------------------------------------------------------------

def _itemprop(soup: BeautifulSoup, prop: str, tag: str = None) -> Optional[BeautifulSoup]:
    """Find first element with given itemprop value, optionally restricted to tag."""
    kwargs = {"attrs": {"itemprop": prop}}
    if tag:
        return soup.find(tag, **kwargs)
    return soup.find(attrs={"itemprop": prop})


def _parse_cook_time(soup: BeautifulSoup) -> Optional[str]:
    """Return human-readable cook time from ISO 8601 duration meta tag."""
    for prop in ("cookTime", "totalTime", "prepTime"):
        el = _itemprop(soup, prop)
        if el:
            iso = el.get("content", "")
            if iso:
                return _iso8601_to_human(iso)
    return None


def _iso8601_to_human(duration: str) -> str:
    """Convert 'PT1H30M' → '1 ч. 30 мин.', 'PT45M' → '45 мин.'"""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration)
    if not m:
        return duration
    hours, mins = int(m.group(1) or 0), int(m.group(2) or 0)
    parts = []
    if hours:
        parts.append(f"{hours} ч.")
    if mins:
        parts.append(f"{mins} мин.")
    return " ".join(parts) if parts else duration


def _parse_servings(soup: BeautifulSoup) -> Optional[int]:
    el = _itemprop(soup, "recipeYield")
    if el:
        text = el.get_text(strip=True)
        m = re.search(r"\d+", text)
        if m:
            return int(m.group())
    return None


def _parse_ingredients(soup: BeautifulSoup) -> list[dict]:
    """Parse li[itemprop='recipeIngredient'] elements."""
    result: list[dict] = []
    for li in soup.find_all(attrs={"itemprop": "recipeIngredient"}):
        link = li.find("a")
        name = link.get_text(strip=True) if link else li.get_text(strip=True)
        if not name:
            continue

        # Remaining text after the link = quantity + unit
        rest = li.get_text(separator=" ", strip=True).replace(name, "").strip()
        # Normalise whitespace
        rest = re.sub(r"\s+", " ", rest)

        ingredient: dict = {"name": name}
        qty_match = re.match(r"^([\d.,/½¼¾]+)\s*(.*)$", rest)
        if qty_match:
            ingredient["quantity"] = qty_match.group(1)
            unit = qty_match.group(2).strip("() ")
            if unit:
                ingredient["unit"] = unit
        elif rest:
            ingredient["unit"] = rest  # "По вкусу", "по желанию", etc.

        result.append(ingredient)
    return result


def _parse_steps(soup: BeautifulSoup) -> list[dict]:
    """Parse div.instruction elements inside div.instructions."""
    instr_div = soup.find("div", class_="instructions")
    if not instr_div:
        # Fallback: single recipeInstructions block → one step
        el = _itemprop(soup, "recipeInstructions")
        if el:
            text = el.get_text(" ", strip=True)
            if text:
                return [{"text": text}]
        return []

    steps: list[dict] = []
    for div in instr_div.find_all("div", class_="instruction"):
        text = div.get_text(" ", strip=True)
        img = div.find("img")
        step: dict = {"text": text}
        if img and img.get("src"):
            step["photo"] = img["src"]
        if text:
            steps.append(step)
    return steps


def _parse_nutrition(soup: BeautifulSoup) -> dict:
    """Parse КБЖУ using Schema.org nutrition microdata (values per 100g)."""
    mapping = {
        "calories":            ("calories", "kcal"),
        "proteinContent":      ("proteins", "g"),
        "fatContent":          ("fats",     "g"),
        "carbohydrateContent": ("carbs",    "g"),
    }
    nutrition: dict = {}
    for itemprop_name, (field, unit) in mapping.items():
        el = _itemprop(soup, itemprop_name)
        if el:
            raw = el.get_text(strip=True)  # e.g. "162 ккал" or "6 г"
            num = re.search(r"[\d.,]+", raw)
            if num:
                nutrition[field] = {
                    "value": num.group().replace(",", "."),
                    "unit": unit,
                }
    return nutrition


def _parse_meal_type(soup: BeautifulSoup) -> Optional[str]:
    """Extract meal type from the Назначение block."""
    naznach_span = soup.find("span", class_="b", string=re.compile(r"Назначение", re.I))
    if not naznach_span:
        return None
    container = naznach_span.parent
    if not container:
        return None
    text = container.get_text(separator=" ", strip=True).lower()
    for keyword, meal_type in MEAL_TYPE_MAP.items():
        if keyword in text:
            return meal_type
    return None


def _parse_image(soup: BeautifulSoup) -> Optional[str]:
    """Return URL of the main dish photo."""
    # Prefer img with itemprop="image" that has a /main/ URL
    for img in soup.find_all("img", attrs={"itemprop": "image"}):
        src = img.get("src", "")
        if "/main/" in src:
            return src
    # Fallback: any img with /main/ in URL
    img = soup.find("img", src=re.compile(r"img\.povar\.ru/main/"))
    return img["src"] if img else None


# ---------------------------------------------------------------------------
# Full recipe page
# ---------------------------------------------------------------------------

def parse_recipe(url: str, cuisine_label: str, country: str) -> Optional[dict]:
    soup = fetch(url, delay=0.7)
    if not soup:
        return None

    # Title
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        return None

    ingredients = _parse_ingredients(soup)
    if len(ingredients) < 2:
        return None  # Likely a scraping error

    meal_type = _parse_meal_type(soup)
    categories = [cuisine_label]
    if meal_type:
        categories.append(meal_type)

    return {
        "title":        title,
        "cook_time":    _parse_cook_time(soup),
        "servings":     _parse_servings(soup),
        "meal_type":    meal_type,       # None → classified by nutritionist agent
        "ingredients":  ingredients,
        "steps":        _parse_steps(soup),
        "nutrition":    _parse_nutrition(soup),
        "categories":   categories,
        "image_url":    _parse_image(soup),
        "source_url":   url,
        "country":      country,
        "is_custom":    False,
        "is_published": True,
    }


# ---------------------------------------------------------------------------
# Main scraping loop
# ---------------------------------------------------------------------------

def scrape_all(pages_override: Optional[int] = None) -> list[dict]:
    all_recipes: list[dict] = []

    for label, cfg in CUISINE_CONFIG.items():
        pages = pages_override if pages_override is not None else cfg["pages"]
        logger.info("=== %s (up to %d list pages, ~%d URLs) ===", label, pages, pages * 40)

        urls = collect_recipe_urls(cfg["slug"], pages)
        logger.info("%s: %d recipe URLs collected", label, len(urls))

        for url in urls:
            recipe = parse_recipe(url, label, cfg["country"])
            if recipe:
                all_recipes.append(recipe)
                nut = recipe["nutrition"]
                cal = nut.get("calories", {}).get("value", "?")
                mt = recipe.get("meal_type") or "—"
                logger.info(
                    "[total %d] %-50s  cal=%s  meal=%s",
                    len(all_recipes), recipe["title"][:50], cal, mt,
                )
            else:
                logger.debug("SKIP %s", url)

        logger.info("%s done — total recipes so far: %d", label, len(all_recipes))

    return all_recipes


def main():
    parser = argparse.ArgumentParser(description="Scrape recipes from povar.ru")
    parser.add_argument("--pages", type=int, default=None, help="Pages per cuisine (overrides config)")
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path(__file__).parent / "scraped_recipes.json"),
    )
    args = parser.parse_args()

    recipes = scrape_all(pages_override=args.pages)

    out = Path(args.output)
    out.write_text(json.dumps(recipes, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %d recipes → %s", len(recipes), out)


if __name__ == "__main__":
    main()
