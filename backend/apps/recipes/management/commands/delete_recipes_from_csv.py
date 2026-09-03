"""Удалить рецепты по списку из CSV (колонки id, Рецепт, Ссылка).

Удаляет ровно те рецепты, что перечислены в CSV. Для безопасности сверяет
rid из ссылки CSV с rid в source_url рецепта: если id есть, но rid не совпал
(id мог сдвинуться) — рецепт пропускается и попадает в отчёт «несовпадения».

ВНИМАНИЕ: удаление каскадно уносит menu.MenuItem (on_delete=CASCADE) — блюда
исчезнут из уже сгенерированных меню. Diary — SET_NULL (запись остаётся,
recipe обнуляется). Операция необратима — ПЕРЕД --apply сделай бэкап БД.

    docker compose exec -T backend python manage.py delete_recipes_from_csv            # dry-run
    docker compose exec -T backend python manage.py delete_recipes_from_csv --apply
    docker compose exec -T backend python manage.py delete_recipes_from_csv --file /path.csv --apply
"""

import csv
import os
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.recipes.models import Recipe

_RID_RE = re.compile(r"rid=(\d+)")


def _default_csv_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "seed", "recipes_to_delete.csv")


class Command(BaseCommand):
    help = "Удалить рецепты по списку из CSV (id + ссылка). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Выполнить (иначе dry-run).")
        parser.add_argument("--file", default=_default_csv_path(), help="CSV со столбцами id, Ссылка.")
        parser.add_argument(
            "--ignore-rid",
            action="store_true",
            help="Не сверять rid ссылки с source_url (удалять строго по id).",
        )

    def handle(self, *args, **opts):
        apply = opts["apply"]
        path = opts["file"]
        ignore_rid = opts["ignore_rid"]

        # MG_UNUSABLE: разделитель определяем по шапке, а не полагаемся на
        # запятую. Выгрузка mg_export_recipes_xlsx --csv пишет через «;» (так
        # Excel открывает файл сразу по столбцам), и при чтении запятой вся
        # строка стала бы одним полем с именем «ID;Название;…» — команда
        # сообщила бы «в CSV записей с id: 0» и молча ничего не удалила.
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                head = f.readline()
                f.seek(0)
                delimiter = ";" if head.count(";") > head.count(",") else ","
                rows = list(csv.DictReader(f, delimiter=delimiter))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Не удалось прочитать CSV {path}: {e}"))
            return

        want = {}  # id -> rid (из ссылки), rid может быть None
        for row in rows:
            # «ID» — так колонка называется в выгрузке для редактора; «id» —
            # в списках, собранных руками. Читаем оба написания.
            rid_str = (row.get("id") or row.get("ID") or "").strip()
            if not rid_str.isdigit():
                continue
            link = row.get("Ссылка") or row.get("ссылка") or row.get("url") or ""
            m = _RID_RE.search(link)
            want[int(rid_str)] = m.group(1) if m else None

        self.stdout.write(f"В CSV записей с id: {len(want)}.")

        found = {r.id: r for r in Recipe.objects.filter(id__in=list(want.keys())).only("id", "title", "source_url")}
        not_in_db = [i for i in want if i not in found]

        to_delete = []
        mismatch = []
        for rid_id, r in found.items():
            csv_rid = want[rid_id]
            if ignore_rid or not csv_rid:
                to_delete.append(rid_id)
                continue
            m = _RID_RE.search(r.source_url or "")
            db_rid = m.group(1) if m else None
            if db_rid == csv_rid:
                to_delete.append(rid_id)
            else:
                mismatch.append((rid_id, csv_rid, db_rid, r.title[:40]))

        # каскад по меню
        try:
            from apps.menu.models import MenuItem

            menu_items = MenuItem.objects.filter(recipe_id__in=to_delete).count()
        except Exception:
            menu_items = -1

        self.stdout.write(f"  найдено в БД:            {len(found)}")
        self.stdout.write(f"  к удалению:              {len(to_delete)}")
        self.stdout.write(f"  нет в БД (пропуск):      {len(not_in_db)}")
        self.stdout.write(f"  rid не совпал (пропуск): {len(mismatch)}")
        self.stdout.write(
            f"  каскадно удалится MenuItem'ов: {menu_items}" if menu_items >= 0 else "  MenuItem: посчитать не удалось"
        )
        for rid_id, csv_rid, db_rid, title in mismatch[:10]:
            self.stdout.write(f"    ! id={rid_id}: csv rid={csv_rid} != db rid={db_rid} ({title})")

        if not apply:
            self.stdout.write(
                self.style.WARNING("DRY-RUN — ничего не удалено. Для удаления: --apply (сделай бэкап БД!).")
            )
            return

        with transaction.atomic():
            deleted, per_model = Recipe.objects.filter(id__in=to_delete).delete()
        self.stdout.write(
            self.style.SUCCESS(f"Готово. Удалено объектов всего: {deleted} (рецептов: {len(to_delete)}).")
        )
        for model, cnt in sorted(per_model.items()):
            self.stdout.write(f"    {model}: {cnt}")
