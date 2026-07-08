"""AI-рерайт шагов рецептов в заданном стиле (по умолчанию: одинокий мужчина 35, инженер).

Для каждого целевого рецепта берёт тексты шагов, просит нейронку переписать их
в нужном тоне, СОХРАНЯЯ все технические детали (времена, температуры, количества,
порядок) и число шагов. Записывает обратно в recipe.steps.

Идемпотентно: переписанные шаги помечаются ключом "rw"=1, повторный прогон их
пропускает. Фильтр --source-url ограничивает набор (напр. menunedeli).

Провайдер AI — из env (get_ai_client). Безопасно: dry-run по умолчанию,
--apply/--limit. Точечное сохранение (update_fields), без перестройки связей.

    docker compose exec -T backend python manage.py rewrite_steps_ai --source-url menunedeli --limit 3
    docker compose exec -T backend python manage.py rewrite_steps_ai --source-url menunedeli --apply
"""

import json

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe

SYSTEM = (
    "Ты — кулинарный редактор. Перепиши шаги рецепта своими словами: живым, "
    "естественным языком, в классическом кулинарном стиле с лёгкой мужской "
    "подачей — просто, уверенно и по-доброму. Без канцелярита, без пафоса и без "
    "сухих «роботизированных» и командно-военных формулировок; это дружеский "
    "рассказ, а не инструкция для робота. Обращайся к читателю на «ты». "
    "Пересказывай каждый шаг ДРУГИМИ словами, но полностью сохрани смысл и все "
    "технические детали (времена, температуры, количества, порядок действий); "
    "не добавляй новых шагов и не выбрасывай существующие. На вход дан JSON-массив "
    "строк — шаги по порядку. Верни JSON-массив строк ТОЙ ЖЕ длины и в том же "
    "порядке. Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений."
)


def _step_texts(recipe):
    out = []
    for s in recipe.steps or []:
        if isinstance(s, dict):
            t = s.get("text")
        else:
            t = s
        out.append(str(t).strip() if t is not None else "")
    return out


def _is_rewritten(recipe):
    for s in recipe.steps or []:
        if isinstance(s, dict) and s.get("rw"):
            return True
    return False


class Command(BaseCommand):
    help = "AI-рерайт шагов рецептов в заданном стиле. По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать (иначе dry-run).")
        parser.add_argument("--limit", type=int, default=0, help="Обработать не более N рецептов (0 = все).")
        parser.add_argument("--source-url", default="", help="Фильтр: source_url содержит эту подстроку.")
        parser.add_argument(
            "--force", action="store_true", help="Переписать заново даже уже переписанные (игнор метки rw)."
        )

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        src = opts["source_url"]
        force = opts["force"]

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

        qs = Recipe.objects.exclude(steps=[]).order_by("id")
        if src:
            qs = qs.filter(source_url__icontains=src)

        targets = []
        for r in qs.only("id", "title", "steps").iterator():
            texts = _step_texts(r)
            if not any(texts):
                continue
            if _is_rewritten(r) and not force:
                continue
            targets.append(r)
            if limit and len(targets) >= limit:
                break

        self.stdout.write(f"Рецептов к рерайту: {len(targets)} (фильтр source_url={src or '—'}).")

        done = failed = 0
        samples = []
        for i, r in enumerate(targets, 1):
            texts = _step_texts(r)
            self.stdout.write(f"  [{i}/{len(targets)}] #{r.id} {r.title[:45]} ({len(texts)} шагов)…")
            self.stdout.flush()
            try:
                raw = client.complete(
                    prompt=json.dumps(texts, ensure_ascii=False), system=SYSTEM, max_tokens=3500, temperature=0.5
                )
                data = _parse_json_loose(raw)
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"    ошибка AI: {e}"))
                failed += 1
                continue
            if (
                not isinstance(data, list)
                or len(data) != len(texts)
                or not all(isinstance(x, str) and x.strip() for x in data)
            ):
                self.stderr.write(self.style.WARNING("    ответ не совпал по формату/длине — пропуск"))
                failed += 1
                continue

            new_steps = [{"text": data[j].strip(), "order": j + 1, "rw": 1} for j in range(len(data))]
            if len(samples) < 3:
                samples.append(f"    #{r.id} шаг1: {new_steps[0]['text'][:120]}")
            if apply:
                r.steps = new_steps
                r._mg_skip_link_rebuild = True
                r.save(update_fields=["steps"])
            done += 1

        for s in samples:
            self.stdout.write(s)
        self.stdout.write(f"Готово. Переписано: {done}; не удалось: {failed}.")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
