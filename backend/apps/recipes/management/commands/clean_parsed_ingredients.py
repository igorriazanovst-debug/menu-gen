"""Чистка ингредиентов у спарсенных рецептов (russianfood) от мусора парсера.

У части рецептов с `source_url` на russianfood в `ingredients` вместе с
реальными продуктами оказались хлебные крошки/категории/теги сайта и
метаданные, например (рецепт #4910):
    ..., "соль", "Рецепты вторых блюд", "Гарниры", "Овощные", "Рагу",
    "Пошаговый", "С фото", "Пост", "Блюда из моркови", "Капуста белокочанная",
    "время приготовления 40 мин", "на 3 порций"
Мусор идёт хвостом после настоящих ингредиентов и НЕ имеет количества.

Детектор (по факту данных russianfood): запись считается мусором, если у неё
НЕТ количества/единицы/грамм И (в тексте нет числа) И выполняется одно из:
  - текст начинается с ЗАГЛАВНОЙ буквы — это категория/тег/крошка
    («Гарниры», «Блюда из моркови», «Капуста белокочанная», «С фото»…);
  - текст — метаданные времени/порций («время приготовления…»,
    «затраты времени…», «на N порций»);
  - текст в явном списке мусора / с мусорным префиксом.
Настоящие строчные ингредиенты без количества («соль», «чеснок», «перец
чёрный молотый») и всё, у чего есть количество/единица/число, сохраняются.

Дополнительно снимает `source_url` (ссылку на источник). Отключается флагом
--keep-source-url.

Связи recipe→product при сохранении не трогаем (`_mg_skip_link_rebuild`);
после --apply пересобери их: командой печатает список id и, при --rebuild-links,
делает пересбор сам (один батч AI-канонизации на затронутые рецепты).

Безопасно: dry-run по умолчанию, запись по --apply, --limit N, --source-url
меняет подстроку фильтра (по умолчанию russianfood).

    docker compose exec -T backend python manage.py clean_parsed_ingredients --limit 5
    docker compose exec -T backend python manage.py clean_parsed_ingredients --apply --rebuild-links
"""

import re

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe

# Метаданные времени/порций russianfood (идут в хвосте состава).
_TIMING_RE = re.compile(r"(врем\w+\s+приготовл|затрат\w+\s+времени|^\s*на\s+\d+\s*порц)", re.IGNORECASE)
# Явный список мусора (на случай, если попадётся строчными).
_JUNK_EXACT = {
    "с фото",
    "с видео",
    "пошаговый",
    "пошаговое",
    "пост",
    "обед",
    "ужин",
    "завтрак",
    "полдник",
    "гарниры",
    "овощные",
    "рагу",
    "каши",
    "вегетарианские",
}
# Мусорные префиксы категорий-ссылок.
_JUNK_PREFIX = ("рецепт", "блюда из")
_STRIP_CHARS = " \t.,;:-—– "


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _ing_text(ing):
    if isinstance(ing, dict):
        return (ing.get("name") or ing.get("raw") or "").strip()
    return str(ing or "").strip()


def _has_measure(ing):
    if not isinstance(ing, dict):
        return False
    q = str(ing.get("quantity") or "").strip()
    u = str(ing.get("unit") or "").strip()
    g = ing.get("grams")
    return bool(q) or bool(u) or (g not in (None, "", 0))


def is_garbage(ing):
    """True — запись похожа на мусор парсера (категория/тег/метаданные)."""
    text = _ing_text(ing)
    if not text:
        return True  # пустой ингредиент — тоже мусор
    if _TIMING_RE.search(text):
        return True
    if _has_measure(ing):
        return False
    if re.search(r"\d", text):
        return False  # есть число в тексте — вероятно, реальный (raw с количеством)
    if text[:1].isupper():
        return True  # категория/тег/крошка с Заглавной
    low = _norm(text)
    if low in _JUNK_EXACT or low.startswith(_JUNK_PREFIX):
        return True
    return False


def _clean_kept(ing):
    """Косметика сохранённой записи: снять хвостовую пунктуацию у name."""
    if isinstance(ing, dict) and ing.get("name"):
        ing = dict(ing)
        ing["name"] = ing["name"].strip(_STRIP_CHARS) or ing["name"]
    return ing


class Command(BaseCommand):
    help = "Чистка ингредиентов спарсенных рецептов (russianfood) от мусора + снятие source_url. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N рецептов (0 = все).")
        parser.add_argument("--source-url", default="russianfood", help="Фильтр: source_url содержит подстроку.")
        parser.add_argument("--keep-source-url", action="store_true", help="НЕ снимать ссылку на источник.")
        parser.add_argument(
            "--rebuild-links", action="store_true", help="После --apply пересобрать recipe→product (AI-канонизация)."
        )

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        src = opts["source_url"]
        keep_url = opts["keep_source_url"]
        rebuild = opts["rebuild_links"]

        qs = Recipe.objects.filter(source_url__icontains=src).order_by("id")

        changed_ids = []
        total_removed = 0
        samples = []
        scanned = 0
        for r in qs.only("id", "title", "ingredients", "source_url").iterator():
            ings = r.ingredients or []
            if not isinstance(ings, list):
                continue
            scanned += 1
            kept, removed = [], []
            for ing in ings:
                if is_garbage(ing):
                    removed.append(_ing_text(ing))
                else:
                    kept.append(_clean_kept(ing))
            if not removed and (keep_url or not r.source_url):
                continue  # нечего менять

            total_removed += len(removed)
            changed_ids.append(r.id)
            if len(samples) < 8:
                samples.append(
                    "  #%d %s\n     оставлено %d, убрано %d: %s"
                    % (r.id, r.title[:48], len(kept), len(removed), ", ".join(removed[:12]))
                )

            if apply:
                r.ingredients = kept
                fields = ["ingredients"]
                if not keep_url and r.source_url:
                    r.source_url = ""
                    fields.append("source_url")
                r._mg_skip_link_rebuild = True
                r.save(update_fields=fields)
            if limit and len(changed_ids) >= limit:
                break

        for s in samples:
            self.stdout.write(s)
        self.stdout.write(
            "Просмотрено: %d; к изменению: %d рецептов; мусорных ингредиентов: %d."
            % (scanned, len(changed_ids), total_removed)
        )
        self.stdout.write("source_url: %s" % ("оставлен (--keep-source-url)" if keep_url else "снят у изменённых"))

        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
            return

        self.stdout.write(self.style.SUCCESS("Готово. Изменено рецептов: %d." % len(changed_ids)))
        if changed_ids and not rebuild:
            self.stdout.write(
                "Пересобери связи: mg_backfill_recipe_products --force --recipe "
                + " ".join(map(str, changed_ids[:200]))
            )
        if changed_ids and rebuild:
            self.stdout.write(">>> Пересбор recipe→product (AI-канонизация)…")
            from apps.recipes.recipe_products import backfill

            stats = backfill(force=True, recipe_ids=changed_ids, log=lambda m: self.stdout.write(str(m)))
            self.stdout.write(self.style.SUCCESS("Связи пересобраны: %s" % stats))
