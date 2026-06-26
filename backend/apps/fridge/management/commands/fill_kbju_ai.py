"""Заполнить КБЖУ продуктам без него через AI (длинный хвост из ингредиентов).

Берёт продукты с пустым nutrition и просит AI оценить КБЖУ на 100 г. Несъедобное
(бытовая химия, посуда, мусорные названия) AI помечает food=false — такие
пропускаем. Значения валидируются (правдоподобные диапазоны), иначе пропуск.

Безопасно: по умолчанию DRY-RUN (только показывает, ничего не пишет и не тратит
запись в БД); запись — флагом --apply. Идемпотентно (повторный запуск берёт
только то, что ещё без КБЖУ). --limit — обработать только N продуктов (удобно
для тестовой партии и контроля стоимости).

    docker compose exec -T backend python manage.py fill_kbju_ai --limit 50          # dry-run, 50 шт
    docker compose exec -T backend python manage.py fill_kbju_ai --limit 50 --apply
    docker compose exec -T backend python manage.py fill_kbju_ai --apply             # весь хвост
"""

import json

from django.core.management.base import BaseCommand

from apps.fridge.models import Product

SYSTEM = (
    "Ты — нутрициолог. На вход дан JSON-массив объектов {i, name} — названия "
    "продуктов питания. Для каждого верни КБЖУ на 100 г съедобной части как "
    "JSON-массив объектов {i, kcal, protein, fat, carb}: kcal — целое число "
    "(ккал), protein/fat/carb — граммы (число, можно дробное). Если позиция НЕ "
    "еда (бытовая химия, посуда, упаковка, бессмысленное название) — верни "
    '{i, food: false}. Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений.'
)


def _has_kbju(p):
    return isinstance(p.nutrition, dict) and len(p.nutrition) > 0


def _plausible(kcal, prot, fat, carb):
    """Грубая валидация: отсечь явный бред."""
    try:
        kcal = float(kcal)
        prot = float(prot)
        fat = float(fat)
        carb = float(carb)
    except (TypeError, ValueError):
        return None
    if not (0 <= kcal <= 1000):
        return None
    if not all(0 <= x <= 100 for x in (prot, fat, carb)):
        return None
    return round(kcal), round(prot, 1), round(fat, 1), round(carb, 1)


class Command(BaseCommand):
    help = "Заполнить КБЖУ продуктам без него через AI. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать результат (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N продуктов (0 = все).")
        parser.add_argument("--batch", type=int, default=20, help="Размер чанка для одного запроса к AI.")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        batch = max(1, opts["batch"])

        try:
            from apps.common.ai_provider import get_ai_client

            client = get_ai_client()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"AI-клиент недоступен: {e}"))
            return
        try:
            from apps.fridge.services import _parse_json_loose
        except Exception:
            _parse_json_loose = None
        if _parse_json_loose is None:
            self.stderr.write(self.style.ERROR("Парсер JSON недоступен (_parse_json_loose)."))
            return

        targets = [p for p in Product.objects.all().order_by("id") if not _has_kbju(p)]
        if limit > 0:
            targets = targets[:limit]
        self.stdout.write(f"Продуктов без КБЖУ к обработке: {len(targets)} (batch={batch}).")

        filled = not_food = failed = 0
        samples = []
        nchunks = (len(targets) + batch - 1) // batch

        for base in range(0, len(targets), batch):
            grp = targets[base : base + batch]
            # живой прогресс: длинный прогон не должен выглядеть зависшим
            self.stdout.write(
                f"  чанк {base // batch + 1}/{nchunks} (заполнено: {filled}, не еда: {not_food})…"
            )
            self.stdout.flush()
            payload = json.dumps([{"i": i, "name": p.name} for i, p in enumerate(grp)], ensure_ascii=False)
            try:
                raw = client.complete(prompt=payload, system=SYSTEM, max_tokens=3000, temperature=0.0)
                data = _parse_json_loose(raw)
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"  чанк {base // batch + 1}: ошибка AI: {e}"))
                failed += len(grp)
                continue
            if not isinstance(data, list):
                failed += len(grp)
                continue

            by_i = {}
            for d in data:
                if isinstance(d, dict) and "i" in d:
                    try:
                        by_i[int(d["i"])] = d
                    except (TypeError, ValueError):
                        pass

            for idx, p in enumerate(grp):
                d = by_i.get(idx)
                if d is None:
                    failed += 1
                    continue
                if d.get("food") is False:
                    not_food += 1
                    continue
                vals = _plausible(d.get("kcal"), d.get("protein"), d.get("fat"), d.get("carb"))
                if vals is None:
                    failed += 1
                    continue
                kcal, prot, fat, carb = vals
                if apply:
                    p.calories_per_100g = kcal
                    p.nutrition = {"calories": kcal, "proteins": prot, "fats": fat, "carbs": carb}
                    p.save(update_fields=["calories_per_100g", "nutrition"])
                if len(samples) < 20:
                    samples.append(f"  {p.name}: {kcal} ккал / Б{prot} Ж{fat} У{carb}")
                filled += 1

        for s in samples:
            self.stdout.write(s)
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. Заполнено: {filled}; не еда (пропущено): {not_food}; "
                f"не удалось распознать: {failed}."
            )
        )
