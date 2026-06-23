"""
Заменяет чужие картинки russianfood.com на сгенерированные YandexART.

Что делает (по согласованному плану):
  1. Находит спарсенные рецепты с картинкой/ссылкой russianfood.com.
  2. --purge: массово зануляет чужие image_url (старый URL бэкапится в
     povar_raw["orig_image_url"] для отката).
  3. Для рецептов без своей картинки строит промт (шаблон + YandexGPT-слоты:
     описание блюда, посуда, приборы, оттенок) и генерирует изображение
     (YandexART), сохраняет файл в media и проставляет относительный image_url.

Идемпотентна: уже перегенерированные (image_url ведёт на /media/…) пропускаются,
так что прогон можно дробить на батчи через --limit и возобновлять.

Запуск (на сервере — там БД, media и .env с кредами):
  python manage.py regen_russianfood_images --dry-run            # счёт + примеры промтов
  python manage.py regen_russianfood_images --purge              # занулить чужие картинки
  python manage.py regen_russianfood_images --limit 100          # сгенерировать батч 100
  python manage.py regen_russianfood_images                      # сгенерировать всё оставшееся
"""

from __future__ import annotations

import logging
import time
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db.models import Q

logger = logging.getLogger(__name__)

# Рецепт «из russianfood»: спарсен и картинка/ссылка указывает на russianfood.
_RF = Q(image_url__icontains="russianfood") | Q(source_url__icontains="russianfood")
# Нужна генерация: своей картинки ещё нет (null/пусто/всё ещё russianfood).
_NEEDS = Q(image_url__isnull=True) | Q(image_url="") | Q(image_url__icontains="russianfood")


class Command(BaseCommand):
    help = "Заменяет чужие картинки russianfood.com на сгенерированные YandexART."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=False,
                            help="Только посчитать и показать примеры промтов; ничего не менять.")
        parser.add_argument("--purge", action="store_true", default=False,
                            help="Занулить чужие image_url (с бэкапом в povar_raw). Без генерации.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Максимум рецептов для генерации за прогон (0 = без лимита).")
        parser.add_argument("--samples", type=int, default=3,
                            help="Сколько примеров промтов показать в --dry-run.")
        parser.add_argument("--sleep", type=float, default=1.0,
                            help="Пауза между рецептами при генерации, сек.")
        parser.add_argument("--retries", type=int, default=3,
                            help="Повторы генерации на рецепт при ошибке API.")

    # ── helpers ─────────────────────────────────────────────────────────────
    def _base_qs(self):
        from apps.recipes.models import Recipe
        return Recipe.objects.filter(source="parsed").filter(_RF)

    def _save_image(self, data: bytes) -> str:
        """Сохраняет JPEG в media и возвращает относительный image_url."""
        filename = f"recipes/images/{uuid.uuid4().hex}.jpg"
        saved_path = default_storage.save(filename, ContentFile(data))
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        return media_url.rstrip("/") + "/" + saved_path.lstrip("/")

    # ── handle ────────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        purge = opts["purge"]
        limit = opts["limit"]

        base = self._base_qs()
        total_rf = base.count()
        still_foreign = base.filter(image_url__icontains="russianfood").count()
        needs = base.filter(_NEEDS).count()
        done = total_rf - needs

        self.stdout.write(self.style.MIGRATE_HEADING("[regen_russianfood_images]"))
        self.stdout.write(f"  Всего russianfood-рецептов:   {total_rf}")
        self.stdout.write(f"  С чужой картинкой сейчас:      {still_foreign}")
        self.stdout.write(f"  Уже своя картинка:             {done}")
        self.stdout.write(f"  Нужна генерация:               {needs}")

        if dry_run:
            self._dry_run(base, opts["samples"])
            return

        if purge:
            self._purge(base)
            return

        self._generate(base, limit, opts["sleep"], opts["retries"])

    # ── dry-run: count + sample prompts ───────────────────────────────────────
    def _dry_run(self, base, samples: int):
        from apps.recipes.image_prompt import build_prompt

        sample_recipes = list(base.filter(_NEEDS)[: max(0, samples)])
        if not sample_recipes:
            self.stdout.write("  (нет рецептов для примера промта)")
            return
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"  Примеры промтов ({len(sample_recipes)}):"))
        for r in sample_recipes:
            try:
                prompt = build_prompt(r.title, r.ingredients, r.steps, r.dish_type)
            except Exception as exc:  # noqa: BLE001 — диагностический режим
                self.stderr.write(f"  ! «{r.title}»: ошибка построения промта: {exc}")
                continue
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"  • {r.title} (#{r.id}, dish_type={r.dish_type or '-'})"))
            self.stdout.write(f"    {prompt}")

    # ── purge: null foreign image_url with backup ─────────────────────────────
    def _purge(self, base):
        qs = base.filter(image_url__icontains="russianfood")
        n = qs.count()
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(f"  PURGE: зануляю {n} чужих картинок (бэкап в povar_raw)…"))
        purged = 0
        for r in qs.iterator(chunk_size=200):
            old = r.image_url
            raw = r.povar_raw if isinstance(r.povar_raw, dict) else {}
            raw = dict(raw)
            raw.setdefault("orig_image_url", old)
            r.povar_raw = raw
            r.image_url = None
            r.save(update_fields=["image_url", "povar_raw", "updated_at"])
            purged += 1
            if purged % 100 == 0:
                self.stdout.write(f"    …{purged}/{n}")
        self.stdout.write(self.style.SUCCESS(f"  PURGE готово: {purged} занулено."))

    # ── generate: prompt -> YandexART -> media -> image_url ───────────────────
    def _generate(self, base, limit: int, sleep_s: float, retries: int):
        from apps.recipes.image_prompt import build_prompt
        from apps.common.image_gen import generate_image, ImageGenError

        qs = base.filter(_NEEDS).order_by("id")
        if limit and limit > 0:
            qs = qs[:limit]
        targets = list(qs)
        total = len(targets)
        if not total:
            self.stdout.write(self.style.SUCCESS("  Нечего генерировать — всё готово."))
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"  Генерация {total} картинок…"))
        ok = failed = 0
        t0 = time.time()

        for i, r in enumerate(targets, 1):
            try:
                prompt = build_prompt(r.title, r.ingredients, r.steps, r.dish_type)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"  [{i}/{total}] ! «{r.title}» (#{r.id}) промт: {exc}")
                failed += 1
                continue

            data = None
            for attempt in range(1, retries + 1):
                try:
                    data = generate_image(prompt, seed=r.id, width_ratio=1, height_ratio=1)
                    break
                except ImageGenError as exc:
                    if attempt >= retries:
                        self.stderr.write(f"  [{i}/{total}] ! «{r.title}» (#{r.id}) ART: {exc}")
                    else:
                        time.sleep(min(2 ** attempt, 16))
            if data is None:
                failed += 1
                continue

            url = self._save_image(data)
            raw = dict(r.povar_raw) if isinstance(r.povar_raw, dict) else {}
            raw["image_prompt"] = prompt
            r.image_url = url
            r.povar_raw = raw
            r.save(update_fields=["image_url", "povar_raw", "updated_at"])
            ok += 1
            self.stdout.write(f"  [{i}/{total}] ✓ «{r.title}» (#{r.id}) -> {url}")

            if sleep_s > 0 and i < total:
                time.sleep(sleep_s)

        elapsed = time.time() - t0
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"  Готово: ок={ok} ошибок={failed} за {elapsed:.0f}с."
        ))
