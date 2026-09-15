"""MG_CATFIX: разложить по рубрикам то, что осело в «Прочем».

Половина каталога лежит в «Прочем»: 598 записей из 1204 на dev, и 593 из них
используются в рецептах. В списке покупок это видно прямо — «Кальмар»,
«Гребешки», «Бекон сырокопчёный», «Зелёное яблоко», «Крахмал», «Кунжут»,
«Грецкий орех» стоят одной кучей под заголовком «Прочее». Это не мусор, а
нормальные продукты без проставленной рубрики, и чинить тут нечего, кроме
самой рубрики.

Почему моделью, а не правилами. Рубрику задаёт смысл слова, а не его форма:
«Кальмар» — рыба и морепродукты, «Эритрит» — сладости, «Паста для том ям» —
соусы. Список из шестисот названий по правилам не разложить, а ошибка здесь
дёшева и обратима: рубрика меняется одним UPDATE и ничего не удаляет.

Что команда НЕ делает: не переименовывает и не сливает записи. Падежи и
опечатки («Тимьяна», «Лавровых листа», «Чипссы») разбирает dedup_products_ai —
у каждой команды своё дело. Эта только проставляет рубрику, в том числе и
записям с кривыми именами: «Тимьяна» в приправах лучше, чем «Тимьяна» в куче.

Разбирается только общий каталог, видимый в подборщиках: справочник штрих-кодов
(32 тысячи упаковок) скрыт, его рубрики никто не видит, а каждая пачка — платный
запрос.

Неполный разбор итогом не считается: если часть пачек не доехала, команда
скажет, сколько названий в плане отсутствует, и с --apply откажется писать.
Иначе «разложено 40» читалось бы как «остальное и не нуждалось».

По умолчанию — DRY-RUN.

    docker compose exec -T backend python manage.py mg_fix_categories --limit 100
    docker compose exec -T backend python manage.py mg_fix_categories
    docker compose exec -T backend python manage.py mg_fix_categories --apply
"""

import json
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.common.ai_provider import complete_with_retry
from apps.fridge.models import Product
from apps.fridge.visibility import HIDDEN_FROM_PICKERS

SYSTEM = (
    "Тебе дан JSON-массив объектов {i, name} — названия продуктов питания из "
    "каталога. Для каждого верни JSON-массив объектов {i, slug}: slug — ОДНА "
    "рубрика строго из списка ниже. Если название не подходит ни под одну "
    "рубрику или это вообще не еда — верни slug='other'. Не придумывай рубрик "
    "вне списка. Отвечай ТОЛЬКО валидным JSON-массивом, без пояснений.\n"
    "Названия бывают в падеже или с опечаткой («Тимьяна», «Лавровых листа», "
    "«Чипссы») — рубрику всё равно определяй по смыслу слова.\n"
    "Список рубрик: __LISTING__"
)


def targets(limit=0):
    """Записи каталога без рубрики или в «Прочем»."""
    qs = (
        Product.objects.filter(Q(category_fk__slug="other") | Q(category_fk__isnull=True))
        .filter(owner_family__isnull=True)
        .exclude(source__in=HIDDEN_FROM_PICKERS)
        .order_by("id")
    )
    return list(qs[:limit] if limit > 0 else qs)


class Command(BaseCommand):
    help = "MG_CATFIX: проставить рубрики записям каталога из «Прочего». По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать рубрики (иначе только показать).")
        parser.add_argument("--limit", type=int, default=0, help="Разобрать не более N записей (0 = все).")
        parser.add_argument("--batch", type=int, default=25, help="Размер пачки для запроса к модели.")
        parser.add_argument("--show", type=int, default=60, help="Сколько строк плана показать.")

    def handle(self, *args, **opts):
        from apps.recipes.recipe_products import _allowed_categories

        apply_ = opts["apply"]
        batch = max(1, opts["batch"])
        show = opts["show"]

        cats = [(slug, ru, cid) for slug, ru, cid in _allowed_categories()]
        cat_id_by_slug = {slug: cid for slug, _ru, cid in cats}
        ru_by_slug = {slug: ru for slug, ru, _cid in cats}
        listing = ", ".join("%s (%s)" % (s, ru) for s, ru, _ in cats)
        system = SYSTEM.replace("__LISTING__", listing)

        try:
            from apps.common.ai_provider import check_ai_available, get_batch_ai_client

            client = get_batch_ai_client()
            check_ai_available()
        except Exception as exc:
            self.stderr.write(self.style.ERROR("ИИ-провайдер недоступен: %s" % exc))
            self.stderr.write(self.style.ERROR("Проверить настройки: manage.py mg_ai_ping"))
            return

        try:
            from apps.fridge.services import _parse_json_loose
        except Exception:
            self.stderr.write(self.style.ERROR("Парсер JSON недоступен (_parse_json_loose)."))
            return

        rows = targets(opts["limit"])
        self.stdout.write("Записей без рубрики или в «Прочем»: %d (пачка=%d)." % (len(rows), batch))
        if not rows:
            return

        plan = []  # (product, slug)
        failed = 0
        nchunks = (len(rows) + batch - 1) // batch
        for base in range(0, len(rows), batch):
            grp = rows[base : base + batch]
            self.stdout.write("  пачка %d/%d…" % (base // batch + 1, nchunks))
            self.stdout.flush()
            payload = json.dumps([{"i": i, "name": p.name} for i, p in enumerate(grp)], ensure_ascii=False)
            try:
                raw = complete_with_retry(client, prompt=payload, system=system, max_tokens=3000, temperature=0.0)
                data = _parse_json_loose(raw)
            except Exception as exc:
                self.stderr.write(self.style.WARNING("  пачка %d: ошибка ИИ: %s" % (base // batch + 1, exc)))
                failed += 1
                continue
            if not isinstance(data, list):
                failed += 1
                continue
            for d in data:
                if not isinstance(d, dict) or "i" not in d:
                    continue
                try:
                    j = int(d["i"])
                except (TypeError, ValueError):
                    continue
                if not (0 <= j < len(grp)):
                    continue
                slug = (d.get("slug") or "").strip()
                # Рубрика вне списка — ответ модели, а не решение: пропускаем.
                if slug and slug != "other" and slug in cat_id_by_slug:
                    plan.append((grp[j], slug))

        by_slug = Counter(slug for _p, slug in plan)
        self.stdout.write("")
        self.stdout.write("Разложить по рубрикам — %d:" % len(plan))
        for slug, n in by_slug.most_common():
            self.stdout.write("   %-14s %-22s %d" % (slug, ru_by_slug.get(slug, ""), n))

        self.stdout.write("")
        for p, slug in plan[:show]:
            self.stdout.write("   %-8s %-40s → %s" % (p.id, p.name[:40], ru_by_slug.get(slug, slug)))
        if len(plan) > show:
            self.stdout.write("   ... скрыто ещё %d" % (len(plan) - show))

        left = len(rows) - len(plan)
        self.stdout.write("")
        self.stdout.write("Остаётся в «Прочем» — %d: модель рубрики не нашла." % left)

        if failed:
            self.stderr.write(
                self.style.ERROR(
                    "Пачек не разобрано: %d из %d — это примерно %d названий, которых в плане выше НЕТ."
                    % (failed, nchunks, failed * batch)
                )
            )
            if apply_:
                self.stderr.write(
                    self.style.ERROR("Запись отменена: сначала добейтесь полного разбора, потом --apply.")
                )
                return

        if not apply_:
            self.stdout.write("")
            self.stdout.write("DRY-RUN. Ничего не изменено. Записать: --apply")
            return

        with transaction.atomic():
            for p, slug in plan:
                Product.objects.filter(id=p.id).update(category_fk_id=cat_id_by_slug[slug])

        self.stdout.write("")
        self.stdout.write("Рубрик проставлено: %d" % len(plan))
