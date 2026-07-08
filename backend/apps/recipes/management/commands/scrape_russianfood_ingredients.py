"""Скрейп ингредиентов с количествами прямо с russianfood.com (по source_url).

Решает проблему битой кодировки: russianfood отдаёт страницы в windows-1251,
и внешние выгрузки часто ломались (выпадали буквы). Здесь мы читаем страницу
рецепта по его `source_url` и декодируем ЯВНО как cp1251 — текст чистый.

Для каждого целевого рецепта (source_url на russianfood, без граммовки):
  - тянем страницу, парсим таблицу ингредиентов (table.ingr);
  - строим ingredients [{name, quantity, unit, grams}] — grams: точно для
    метрики (г/кг/мл), по таблице типовых весов для шт/стакан/ложка/зубчик/пучок
    (см. import_russianfood_ingredients), "по вкусу" — без grams.

Идемпотентно: рецепты, где граммовка уже есть, пропускаются. Связи
recipe→product при сохранении не перестраиваем (потом mg_backfill_recipe_products).
Вежливо к сайту: пауза между запросами (--delay), ретраи на 403/429.

Безопасно: dry-run по умолчанию, запись по --apply, --limit N.

    docker compose exec -T backend python manage.py scrape_russianfood_ingredients --limit 3
    docker compose exec -T backend python manage.py scrape_russianfood_ingredients --limit 50 --apply
    docker compose exec -T backend python manage.py scrape_russianfood_ingredients --apply
"""

import random
import re
import time

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe

from .import_russianfood_ingredients import _has_grams, _parse_grams

_UA = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]


def _parse_ingredient_line(text):
    """«Рис (у меня басмати) - 200 г» -> {name, quantity, unit}."""
    text = (text or "").strip()
    name, amount = text, ""
    m = re.match(r"^(.*?)\s+[-–—]\s+(.+)$", text)
    if m:
        name = m.group(1).strip()
        amount = m.group(2).strip()
    nm = re.match(r"^(.*?)\s*\([^)]*\)\s*$", name)
    if nm and nm.group(1).strip():
        name = nm.group(1).strip()
    quantity, unit = "", ""
    if amount:
        am = re.match(r"^(.*?)\s*\([^)]*\)\s*$", amount)
        amount_core = am.group(1).strip() if am else amount
        qm = re.match(r"^([\d]+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?)\s*(.*)$", amount_core)
        if qm:
            quantity = qm.group(1).strip()
            unit = qm.group(2).strip()
        else:
            unit = amount_core
    return {"name": name, "quantity": quantity, "unit": unit}


class Command(BaseCommand):
    help = "Скрейп ингредиентов с количествами с russianfood (cp1251). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать результат (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N рецептов (0 = все).")
        parser.add_argument("--delay", type=float, default=1.0, help="Базовая пауза между запросами, сек.")

    def _fetch(self, session, url, delay):
        import requests

        for attempt, wait in enumerate([0, 5, 15, 40]):
            if wait:
                time.sleep(wait * (0.7 + 0.6 * random.random()))
            time.sleep(delay * (0.5 + random.random()))
            try:
                resp = session.get(url, headers={"User-Agent": random.choice(_UA)}, timeout=20)
            except requests.RequestException as exc:
                self.stderr.write(self.style.WARNING(f"    сеть: {exc}"))
                continue
            if resp.status_code in (403, 429):
                self.stderr.write(self.style.WARNING(f"    HTTP {resp.status_code}, ретрай…"))
                continue
            if resp.status_code != 200:
                self.stderr.write(self.style.WARNING(f"    HTTP {resp.status_code}: {url}"))
                return None
            return resp.content.decode("windows-1251", errors="replace")
        return None

    def _extract(self, html):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        out = []
        for td in soup.select("table.ingr td.padding_r"):
            text = td.get_text(strip=True)
            if not text:
                continue
            ing = _parse_ingredient_line(text)
            if ing["name"]:
                out.append(ing)
        return out

    def handle(self, *args, **opts):
        try:
            import requests
            from bs4 import BeautifulSoup  # noqa: F401  (используется в _extract)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Нет requests/bs4: {e}"))
            return

        apply = opts["apply"]
        limit = opts["limit"]
        delay = max(0.2, opts["delay"])

        targets = []
        for r in (
            Recipe.objects.filter(source_url__icontains="russianfood")
            .exclude(source_url__isnull=True)
            .exclude(source_url="")
            .order_by("id")
            .iterator()
        ):
            if _has_grams(r):
                continue
            targets.append(r)
            if limit and len(targets) >= limit:
                break

        self.stdout.write(f"Рецептов к обработке: {len(targets)} (delay={delay}s, apply={apply}).")

        session = requests.Session()
        updated = no_ings = failed = 0
        rows_total = rows_grams = 0
        samples = []

        for i, recipe in enumerate(targets, 1):
            self.stdout.write(f"  [{i}/{len(targets)}] #{recipe.id} {recipe.title[:45]}…")
            self.stdout.flush()
            html = self._fetch(session, recipe.source_url, delay)
            if not html:
                failed += 1
                continue
            parsed = self._extract(html)
            if not parsed:
                no_ings += 1
                continue

            new_ings = []
            g_here = 0
            for ing in parsed:
                q = ing["quantity"]
                u = ing["unit"]
                grams = _parse_grams(ing["name"], (q + " " + u).strip())
                rows_total += 1
                if grams is not None:
                    rows_grams += 1
                    g_here += 1
                new_ings.append({"name": ing["name"][:255], "quantity": q[:64], "unit": u[:50], "grams": grams})

            if len(samples) < 8:
                samples.append(f"    #{recipe.id}: {len(new_ings)} ингр., с граммами {g_here}")
            if apply:
                recipe.ingredients = new_ings
                recipe._mg_skip_link_rebuild = True
                recipe.save(update_fields=["ingredients"])
            updated += 1

        for s in samples:
            self.stdout.write(s)
        cover = (100.0 * rows_grams / rows_total) if rows_total else 0.0
        self.stdout.write(f"Обновлено: {updated}; без ингредиентов на странице: {no_ings}; ошибок загрузки: {failed}.")
        self.stdout.write(f"Ингредиентов: {rows_total}, с граммовкой: {rows_grams} ({cover:.0f}%).")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
        else:
            self.stdout.write(
                self.style.SUCCESS("Готово. Далее: mg_backfill_recipe_products и fill_recipe_kbju_ai --apply.")
            )
