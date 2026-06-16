#!/usr/bin/env python3
"""
Локальный скрапер гарниров с russianfood.com.
Не требует Django — только: pip install requests beautifulsoup4

Запуск:
  python scrape_russianfood_local.py                        # все страницы
  python scrape_russianfood_local.py --pages 5              # первые 5 страниц
  python scrape_russianfood_local.py --out garnishes.json   # свой файл вывода
  python scrape_russianfood_local.py --resume               # продолжить с прерванного места

Результат: garnishes.json (или --out) — массив объектов рецептов.
"""

import argparse
import json
import logging
import random
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_URL = "https://www.russianfood.com"
LIST_URL = "https://www.russianfood.com/recipes/bytype/?fid=17"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _get(url: str, delay: float) -> BeautifulSoup | None:
    retry_waits = [15, 45, 90]
    for attempt, wait in enumerate([0] + retry_waits):
        if wait:
            log.warning("403/429 — пауза %ds (попытка %d)", wait, attempt + 1)
            time.sleep(wait)
        try:
            resp = SESSION.get(url, timeout=20)
            if resp.status_code in (403, 429):
                log.warning("HTTP %s: %s", resp.status_code, url)
                continue
            if resp.status_code != 200:
                log.warning("HTTP %s: %s", resp.status_code, url)
                return None
            time.sleep(delay * (0.5 + random.random()))
            return BeautifulSoup(resp.content, "html.parser", from_encoding="windows-1251")
        except Exception as exc:
            log.error("Ошибка: %s — %s", url, exc)
    return None


def collect_urls(max_pages: int, delay: float) -> list[str]:
    all_urls: list[str] = []
    page_url: str | None = LIST_URL
    page_num = 0

    while page_url:
        page_num += 1
        log.info("Листинг стр.%d: %s", page_num, page_url)
        soup = _get(page_url, delay)
        if not soup:
            log.error("Не удалось загрузить листинг стр.%d", page_num)
            break

        seen = set(all_urls)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "recipe.php" in href and "rid=" in href:
                full = BASE_URL + href if not href.startswith("http") else href
                if full not in seen:
                    seen.add(full)
                    all_urls.append(full)

        log.info("  → найдено ссылок всего: %d", len(all_urls))

        next_url = None
        for a in soup.find_all("a", href=True):
            if "Следующая" in a.get_text():
                href = a["href"]
                if "page=" in href:
                    next_url = (BASE_URL + href).split("#")[0]
                    break

        if max_pages and page_num >= max_pages:
            break
        page_url = next_url

    return all_urls


def parse_recipe(url: str, delay: float) -> dict | None:
    soup = _get(url, delay)
    if not soup:
        return None

    data: dict = {"source_url": url}

    h1 = soup.find("h1")
    if not h1:
        return None
    data["title"] = h1.get_text(strip=True)

    # og:image
    og_img = soup.select_one("meta[property='og:image']")
    if og_img:
        src = og_img.get("content", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            data["image_url"] = src

    # время и порции из комментария
    raw_html = str(soup)
    m = re.search(r"время приготовления\s+(\d+)\s*мин.*?на\s+(\d+)\s*пор", raw_html, re.I)
    if m:
        data["cook_time_min"] = int(m.group(1))
        data["cook_time"] = f"{m.group(1)} мин."
        data["servings"] = int(m.group(2))

    # ингредиенты из <meta description>
    desc_meta = soup.select_one("meta[name='description']")
    if desc_meta:
        desc = desc_meta.get("content", "")
        cm = re.search(r"[сc]остав\s*:\s*(.+)", desc, re.I)
        if cm:
            raw_ingr = cm.group(1).strip()
            parts = re.split(r",\s*(?![^(]*\))", raw_ingr)
            ingredients = []
            for part in parts:
                part = part.strip().rstrip(".")
                if part and len(part) > 1:
                    ingredients.append({"raw": part})
            if ingredients:
                data["ingredients"] = ingredients

    # шаги из div.step_n
    step_els = soup.select("div.step_n")
    if step_els:
        steps = []
        for i, el in enumerate(step_els):
            text = el.get_text(strip=True)
            if text:
                steps.append({"step": i + 1, "text": text})
        if steps:
            data["steps"] = steps

    return data


def main():
    parser = argparse.ArgumentParser(description="Скрапер гарниров russianfood.com")
    parser.add_argument("--out", default="garnishes.json")
    parser.add_argument("--pages", type=int, default=0, help="0 = все страницы")
    parser.add_argument("--delay", type=float, default=3.0, help="базовая пауза в секундах")
    parser.add_argument("--resume", action="store_true", help="продолжить: пропустить уже сохранённые URL")
    args = parser.parse_args()

    out_path = Path(args.out)

    # загрузить уже сохранённые
    existing: list[dict] = []
    existing_urls: set[str] = set()
    if args.resume and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing_urls = {r["source_url"] for r in existing}
        log.info("Режим RESUME: уже сохранено %d рецептов", len(existing))

    log.info("Собираем URL рецептов (delay=%.1fs)...", args.delay)
    urls = collect_urls(args.pages, args.delay)
    log.info("Всего URL: %d", len(urls))

    results = list(existing)
    ok = 0
    fail = 0
    skip = 0

    t0 = time.time()

    for i, url in enumerate(urls, 1):
        if url in existing_urls:
            skip += 1
            continue

        log.info("[%d/%d] %s", i, len(urls), url)
        data = parse_recipe(url, args.delay)

        if not data or not data.get("title"):
            log.warning("  FAIL")
            fail += 1
        else:
            log.info("  OK: «%s» ингр=%d шаги=%d",
                     data["title"],
                     len(data.get("ingredients", [])),
                     len(data.get("steps", [])))
            results.append(data)
            existing_urls.add(url)
            ok += 1

        # сохраняем каждые 10 рецептов
        if (ok + fail) % 10 == 0:
            out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            elapsed = time.time() - t0
            log.info("  → checkpoint: сохранено %d, ошибок %d, пропущено %d (%.0fс)", ok, fail, skip, elapsed)

    # финальное сохранение
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed = time.time() - t0

    log.info("=" * 60)
    log.info("Итог за %.0fс:", elapsed)
    log.info("  Всего URL:    %d", len(urls))
    log.info("  Пропущено:    %d", skip)
    log.info("  Успешно:      %d", ok)
    log.info("  Ошибок:       %d", fail)
    log.info("  Файл:         %s (%.1f MB)", out_path, out_path.stat().st_size / 1024 / 1024)


if __name__ == "__main__":
    main()
