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
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe


def _default_skip_path():
    return os.path.join(settings.MEDIA_ROOT, "rewrite_skiplist.json")


def _load_skip(path):
    """{id: {id, title, reason}} из файла-скиплиста; пустой при отсутствии/ошибке."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {int(e["id"]): e for e in data if isinstance(e, dict) and "id" in e}
    except Exception:
        return {}


def _save_skip(path, skip):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(skip.values()), f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _complete_with_timeout(client, prompt, system, max_tokens, temperature, timeout):
    """AI-вызов с жёстким лимитом времени: по истечении — TimeoutError,
    зависший поток бросаем (shutdown wait=False), чтобы не блокировать прогон."""
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(client.complete, prompt=prompt, system=system, max_tokens=max_tokens, temperature=temperature)
    try:
        return fut.result(timeout=timeout)
    finally:
        ex.shutdown(wait=False)


SYSTEM = (
    "Ты — кулинарный редактор. Перепиши шаги рецепта своими словами: живым, "
    "естественным языком, в классическом кулинарном стиле, с лёгкой мужской "
    "подачей — просто, уверенно и по-доброму. Без канцелярита, без пафоса и без "
    "сухих «роботизированных» и командно-военных формулировок. Каждый шаг — это "
    "описание конкретных действий ИМЕННО этого шага, пересказанное другими "
    "словами. НЕ добавляй приветствий и вступлений («Привет», «Друзья», «Сегодня "
    "мы приготовим» и т.п.), не комментируй рецепт целиком, не пиши выводов и "
    "оценок. Обращайся к читателю на «ты». Полностью сохрани смысл и все "
    "технические детали (времена, температуры, количества, порядок действий); не "
    "добавляй новых шагов и не выбрасывай существующие. На вход дан JSON-массив "
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
            "--source", default="", help="Фильтр по полю source (own/import/user/parsed). own = «Собственный»."
        )
        parser.add_argument(
            "--force", action="store_true", help="Переписать заново даже уже переписанные (игнор метки rw)."
        )
        parser.add_argument("--full", action="store_true", help="Печатать все шаги целиком (для оценки стиля).")
        parser.add_argument("--timeout", type=float, default=90.0, help="Лимит на один рецепт, сек (потом пропуск).")
        parser.add_argument("--skip-file", default="", help="JSON-скиплист (по умолчанию MEDIA/rewrite_skiplist.json).")
        parser.add_argument(
            "--ignore-skip", action="store_true", help="Не исключать рецепты из скиплиста (попробовать снова)."
        )

    def handle(self, *args, **opts):
        apply = opts["apply"]
        limit = opts["limit"]
        src = opts["source_url"]
        source = opts["source"]
        force = opts["force"]
        full = opts["full"]
        timeout = opts["timeout"]
        skip_path = opts["skip_file"] or _default_skip_path()
        ignore_skip = opts["ignore_skip"]
        skip = _load_skip(skip_path)
        skip_ids = set() if ignore_skip else set(skip.keys())

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
        if source:
            qs = qs.filter(source=source)

        targets = []
        for r in qs.only("id", "title", "steps").iterator():
            texts = _step_texts(r)
            if not any(texts):
                continue
            if _is_rewritten(r) and not force:
                continue
            if r.id in skip_ids:
                continue
            targets.append(r)
            if limit and len(targets) >= limit:
                break

        self.stdout.write(
            f"Рецептов к рерайту: {len(targets)} (фильтр source_url={src or '—'}, "
            f"source={source or '—'}, в скиплисте {len(skip)} — пропускаются)."
        )

        done = failed = 0
        samples = []
        for i, r in enumerate(targets, 1):
            texts = _step_texts(r)
            self.stdout.write(f"  [{i}/{len(targets)}] #{r.id} {r.title[:45]} ({len(texts)} шагов)…")
            self.stdout.flush()
            try:
                raw = _complete_with_timeout(
                    client,
                    prompt=json.dumps(texts, ensure_ascii=False),
                    system=SYSTEM,
                    max_tokens=3500,
                    temperature=0.5,
                    timeout=timeout,
                )
                data = _parse_json_loose(raw)
            except FuturesTimeout:
                self.stderr.write(self.style.WARNING(f"    таймаут {timeout:.0f}s — в скиплист"))
                skip[r.id] = {"id": r.id, "title": r.title, "reason": "timeout"}
                _save_skip(skip_path, skip)
                failed += 1
                continue
            except Exception as e:
                # временная ошибка AI (сеть/шлюз) — НЕ в скиплист, попробуем в другой раз
                self.stderr.write(self.style.WARNING(f"    ошибка AI: {e}"))
                failed += 1
                continue
            if (
                not isinstance(data, list)
                or len(data) != len(texts)
                or not all(isinstance(x, str) and x.strip() for x in data)
            ):
                self.stderr.write(self.style.WARNING("    ответ не по формату/длине — в скиплист"))
                skip[r.id] = {"id": r.id, "title": r.title, "reason": "format"}
                _save_skip(skip_path, skip)
                failed += 1
                continue

            new_steps = [{"text": data[j].strip(), "order": j + 1, "rw": 1} for j in range(len(data))]
            if full:
                self.stdout.write(f"  === #{r.id} {r.title} — все шаги ===")
                for st in new_steps:
                    self.stdout.write(f"  {st['order']}. {st['text']}")
                self.stdout.write("")
            elif len(samples) < 3:
                samples.append(f"    #{r.id} шаг1: {new_steps[0]['text'][:120]}")
            if apply:
                r.steps = new_steps
                r._mg_skip_link_rebuild = True
                r.save(update_fields=["steps"])
            done += 1

        for s in samples:
            self.stdout.write(s)
        self.stdout.write(f"Готово. Переписано: {done}; не удалось: {failed}.")
        self.stdout.write(f"Скиплист (тайм-аут/дроп, пропускаются впредь): {len(skip)} → {skip_path}")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — ничего не записано. Для записи: --apply"))
