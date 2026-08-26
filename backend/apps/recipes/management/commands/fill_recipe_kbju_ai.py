"""Заполнить недостающее КБЖУ рецептам через AI (по составу ингредиентов).

Берёт рецепты, у которых в `nutrition` нет хотя бы одного из макросов
(калории/белки/жиры/углеводы), и просит AI оценить пищевую ценность ГОТОВОГО
блюда НА 100 Г по названию и списку ингредиентов (с граммовкой, если есть).

Заполняет только недостающее — уже проставленные значения не перезаписывает.
Пишет одновременно:
  - объект `nutrition` (плоский, на 100 г): calories/proteins/fats/carbs/sugars;
  - числовые поля per-100g: kcal_per_100g/proteins_per_100g/fats_per_100g/
    carbs_per_100g/sugars_per_100g (только те, что были пусты);
  - per-порционные kcal/proteins/fats/carbs, если задан вес порции portion_g
    (только пустые).

Провайдер AI — из env (apps.common.ai_provider.get_ai_client): не Yandex,
настраивается через AI_PROVIDER=openai (или anthropic) + AI_API_KEY.

Безопасно: по умолчанию DRY-RUN (ничего не пишет). Запись — флагом --apply.
Идемпотентно (повторный прогон берёт только рецепты без полного КБЖУ).
--limit N — обработать не более N рецептов (тестовая партия / контроль стоимости).
--batch M — сколько рецептов слать в одном запросе к AI.

    docker compose exec -T backend python manage.py fill_recipe_kbju_ai --limit 20
    docker compose exec -T backend python manage.py fill_recipe_kbju_ai --limit 20 --apply
    docker compose exec -T backend python manage.py fill_recipe_kbju_ai --apply
"""

import json

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe

# Макросы, наличие которых в nutrition проверяем (на 100 г).
_MACROS = ("calories", "proteins", "fats", "carbs")

SYSTEM = (
    "Ты — нутрициолог. На вход дан JSON-массив блюд "
    "{i, title, ingredients:[{name, grams}]}. Для каждого блюда оцени пищевую "
    "ценность ГОТОВОГО блюда НА 100 Г и верни JSON-массив объектов "
    "{i, kcal, protein, fat, carb, sugar}: kcal — целое число (ккал на 100 г "
    "готового блюда), protein/fat/carb/sugar — граммы на 100 г (число, можно "
    "дробное; sugar — сахара, если оценить нельзя, поставь 0). Учитывай потерю/"
    "набор воды при готовке — оценивай на 100 г готового блюда, а не сырых "
    "продуктов. Если граммовка не указана — оцени по типичному рецепту. "
    "Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений."
)


def _num(v):
    """float или None (терпит вложенный {'value': ...} и строки)."""
    if isinstance(v, dict):
        v = v.get("value")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _needs_kbju(recipe) -> bool:
    """True, если в nutrition отсутствует хотя бы один макрос."""
    nut = recipe.nutrition if isinstance(recipe.nutrition, dict) else {}
    return any(_num(nut.get(k)) is None for k in _MACROS)


def _ingredients(recipe):
    out = []
    for ing in recipe.ingredients or []:
        if not isinstance(ing, dict):
            continue
        name = (ing.get("name") or "").strip()
        if not name:
            continue
        item = {"name": name[:120]}
        grams = _num(ing.get("grams"))
        if grams is not None:
            item["grams"] = round(grams, 1)
        out.append(item)
    return out


def _plausible(kcal, prot, fat, carb, sugar):
    """Грубая валидация значений на 100 г готового блюда; иначе None."""
    try:
        kcal = float(kcal)
        prot = float(prot)
        fat = float(fat)
        carb = float(carb)
    except (TypeError, ValueError):
        return None
    if not (0 <= kcal <= 900):
        return None
    if not all(0 <= x <= 100 for x in (prot, fat, carb)):
        return None
    s = None
    try:
        if sugar is not None:
            s = float(sugar)
            if not (0 <= s <= 100):
                s = None
    except (TypeError, ValueError):
        s = None
    return round(kcal), round(prot, 1), round(fat, 1), round(carb, 1), (round(s, 1) if s is not None else None)


class Command(BaseCommand):
    help = "Заполнить недостающее КБЖУ рецептам через AI (по ингредиентам). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать результат (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N рецептов (0 = все).")
        parser.add_argument("--batch", type=int, default=10, help="Размер чанка для одного запроса к AI.")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        batch = max(1, opts["batch"])

        try:
            from apps.common.ai_provider import get_ai_client

            client = get_ai_client()
            # MG_AIPING: фабрика только собирает клиента и ловит пустой ключ.
            # Неверный ключ виден лишь по ответу сервиса — без запроса команда
            # уходила в прогон и ловила 401 на каждой пачке.
            from apps.common.ai_provider import check_ai_available

            check_ai_available()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"ИИ-провайдер недоступен: {e}"))
            self.stderr.write(self.style.ERROR("Проверить настройки: manage.py mg_ai_ping"))
            return
        try:
            from apps.fridge.services import _parse_json_loose
        except Exception:
            _parse_json_loose = None
        if _parse_json_loose is None:
            self.stderr.write(self.style.ERROR("Парсер JSON недоступен (_parse_json_loose)."))
            return

        targets = []
        skipped_no_ings = 0
        for r in Recipe.objects.all().order_by("id").iterator():
            if not _needs_kbju(r):
                continue
            if not _ingredients(r):
                skipped_no_ings += 1
                continue
            targets.append(r)
            if limit > 0 and len(targets) >= limit:
                break

        self.stdout.write(
            f"Рецептов без полного КБЖУ (с ингредиентами) к обработке: {len(targets)} "
            f"(без ингредиентов пропущено: {skipped_no_ings}, batch={batch})."
        )

        filled = failed = 0
        samples = []
        nchunks = (len(targets) + batch - 1) // batch

        for base in range(0, len(targets), batch):
            grp = targets[base : base + batch]
            self.stdout.write(f"  чанк {base // batch + 1}/{nchunks} (заполнено: {filled})…")
            self.stdout.flush()
            payload = json.dumps(
                [{"i": i, "title": r.title, "ingredients": _ingredients(r)} for i, r in enumerate(grp)],
                ensure_ascii=False,
            )
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

            for idx, r in enumerate(grp):
                d = by_i.get(idx)
                if d is None:
                    failed += 1
                    continue
                vals = _plausible(d.get("kcal"), d.get("protein"), d.get("fat"), d.get("carb"), d.get("sugar"))
                if vals is None:
                    failed += 1
                    continue
                changed = self._apply_recipe(r, vals, apply)
                if changed:
                    filled += 1
                    if len(samples) < 20:
                        kcal, prot, fat, carb, sugar = vals
                        samples.append(f"  #{r.id} {r.title[:40]}: {kcal} ккал / Б{prot} Ж{fat} У{carb}")
                else:
                    failed += 1

        for s in samples:
            self.stdout.write(s)
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. Заполнено: {filled}; не удалось: {failed}; без ингредиентов: {skipped_no_ings}."
            )
        )

    def _apply_recipe(self, recipe, vals, apply) -> bool:
        """Заполнить недостающие значения. Возвращает True, если что-то изменилось."""
        kcal, prot, fat, carb, sugar = vals
        # per-100g значения по ключам nutrition
        ai_by_key = {"calories": kcal, "proteins": prot, "fats": fat, "carbs": carb}
        if sugar is not None:
            ai_by_key["sugars"] = sugar

        nut = dict(recipe.nutrition) if isinstance(recipe.nutrition, dict) else {}
        # итоговые per-100g (существующее приоритетнее AI), + отметка что заполнили
        final = {}
        touched = False
        for key, ai_val in ai_by_key.items():
            existing = _num(nut.get(key))
            if existing is not None:
                final[key] = existing
            else:
                final[key] = ai_val
                nut[key] = ai_val
                touched = True

        # числовые поля per-100g — только пустые
        num_fields = {
            "kcal_per_100g": "calories",
            "proteins_per_100g": "proteins",
            "fats_per_100g": "fats",
            "carbs_per_100g": "carbs",
            "sugars_per_100g": "sugars",
        }
        update_fields = ["nutrition"]
        for field, key in num_fields.items():
            if key not in final:
                continue
            if getattr(recipe, field) is None:
                setattr(recipe, field, final[key])
                update_fields.append(field)
                touched = True

        # per-порционные — только пустые и при известном весе порции
        portion = recipe.portion_g
        if portion:
            per_serv = {
                "kcal": ("calories", 0),
                "proteins": ("proteins", 1),
                "fats": ("fats", 1),
                "carbs": ("carbs", 1),
            }
            for field, (key, ndigits) in per_serv.items():
                if key not in final:
                    continue
                if getattr(recipe, field) is None:
                    val = final[key] * float(portion) / 100.0
                    val = round(val) if ndigits == 0 else round(val, ndigits)
                    setattr(recipe, field, val)
                    update_fields.append(field)
                    touched = True

        if not touched:
            return False
        recipe.nutrition = nut
        if apply:
            # MG_KBJU_AI: КБЖУ не меняет ингредиенты — пропускаем перестройку
            # recipe→product связей (post_save signal) и реклассификацию (save
            # с update_fields её и так не запускает). Точечный save.
            recipe._mg_skip_link_rebuild = True
            recipe.save(update_fields=list(dict.fromkeys(update_fields)))
        return True
