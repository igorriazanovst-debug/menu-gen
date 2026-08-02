"""MG_IMGAUDIT: поиск рецептов с битыми картинками.

Картинка не показывается по трём разным причинам, и лечатся они по-разному:

* ``missing``  — ссылка относительная (``/media/...``), но файла на диске нет.
  Обычно файл не доехал при переносе между серверами.
* ``external`` — ссылка ведёт на чужой хост. Такие переживают переезд плохо:
  внешний сайт мог удалить файл, а ссылки на старый адрес проекта отваливаются,
  когда тот сервер выключают. С ``--check-remote`` каждая проверяется запросом.
* ``empty``    — картинки нет вовсе.

Команда только читает БД и диск, ничего не меняет.

Запуск:
    python manage.py check_recipe_images
    python manage.py check_recipe_images --check-remote   # ещё и опрос внешних
    python manage.py check_recipe_images --list-ok        # показать и целые
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.management.base import BaseCommand

_TIMEOUT = 10


def local_path(image_url: str) -> Path | None:
    """Относительная ссылка → путь на диске. Для внешних ссылок — None."""
    url = (image_url or "").strip()
    if not url or url.lower().startswith(("http://", "https://")):
        return None

    path = unquote(urlparse(url).path or url)
    media_url = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").rstrip("/")
    if media_url and path.startswith(media_url):
        path = path[len(media_url) :]
    return Path(settings.MEDIA_ROOT) / path.lstrip("/")


def join_steps(steps) -> str:
    """Шаги приготовления → одна ячейка: «1) … 2) …».

    В БД шаг бывает и строкой, и объектом {"text": …, "photo": …} — формат
    зависит от того, каким импортом рецепт приехал. Переводы строк убираем:
    внутри ячейки они ломают чтение CSV частью программ.
    """
    out = []
    for item in steps or []:
        if isinstance(item, dict):
            text = item.get("text") or ""
        else:
            text = str(item or "")
        text = " ".join(text.split())
        if text:
            out.append(f"{len(out) + 1}) {text}")
    return " ".join(out)


class Command(BaseCommand):
    help = "MG_IMGAUDIT: показывает рецепты, у которых картинка не отображается."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-remote",
            action="store_true",
            default=False,
            help="Опрашивать внешние ссылки (медленно: по запросу на картинку)",
        )
        parser.add_argument("--list-ok", action="store_true", default=False, help="Показывать и целые картинки")
        parser.add_argument("--limit", type=int, default=None, help="Проверить только первые N рецептов")
        parser.add_argument(
            "--export-empty",
            metavar="ПУТЬ",
            default=None,
            help="Выгрузить CSV со списком рецептов без фото (для ручной загрузки картинок)",
        )

    def handle(self, *args, **opts):
        from apps.recipes.models import Recipe

        qs = Recipe.objects.order_by("title").values_list(
            "id", "title", "image_url", "dish_type", "country", "source", "source_url", "steps"
        )
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        missing: list[tuple[int, str, str]] = []
        external: list[tuple[int, str, str]] = []
        empty: list[tuple] = []
        ok = 0

        for pk, title, image_url, dish_type, country, source, source_url, steps in qs:
            url = (image_url or "").strip()
            if not url:
                empty.append((pk, title, dish_type, country, source, source_url, steps))
                continue

            path = local_path(url)
            if path is None:
                external.append((pk, title, url))
            elif path.is_file():
                ok += 1
                if opts["list_ok"]:
                    self.stdout.write(f"  ok      {pk:>5}  {title[:50]}")
            else:
                missing.append((pk, title, url))

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Всего рецептов:            {ok + len(missing) + len(external) + len(empty)}")
        self.stdout.write(f"Картинка на месте:         {ok}")
        self.stdout.write(f"Файл не найден на диске:   {len(missing)}")
        self.stdout.write(f"Ссылка на внешний хост:    {len(external)}")
        self.stdout.write(f"Картинки нет вовсе:        {len(empty)}")
        self.stdout.write(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")

        if missing:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Файл не найден (ссылка есть, файла нет):"))
            for pk, title, url in missing:
                self.stdout.write(f"  {pk:>5}  {title[:45]:<45}  {url}")

        if external:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Внешние ссылки:"))
            statuses = self._probe(external) if opts["check_remote"] else {}
            for pk, title, url in external:
                mark = f"  [{statuses[pk]}]" if pk in statuses else ""
                self.stdout.write(f"  {pk:>5}  {title[:45]:<45}  {url}{mark}")
            if opts["check_remote"]:
                broken = [pk for pk, status in statuses.items() if status != "200"]
                self.stdout.write(f"  Недоступных внешних: {len(broken)} из {len(external)}")
            else:
                self.stdout.write("  (добавьте --check-remote, чтобы проверить доступность)")

        if opts["export_empty"]:
            self._export_empty(empty, Path(opts["export_empty"]))

        if not missing and not external:
            self.stdout.write(self.style.SUCCESS("\nБитых картинок не найдено."))

    def _export_empty(self, empty, path: Path) -> None:
        """CSV со списком рецептов без фото — рабочий лист для ручной загрузки."""
        import csv

        # utf-8-sig: без BOM Excel открывает кириллицу кракозябрами.
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(
                ["id", "название", "тип блюда", "кухня", "источник", "ссылка на источник", "админка", "рецепт"]
            )
            for pk, title, dish_type, country, source, source_url, steps in empty:
                writer.writerow(
                    [
                        pk,
                        title,
                        dish_type or "",
                        country or "",
                        source or "",
                        source_url or "",
                        f"/admin/recipes/recipe/{pk}/change/",
                        join_steps(steps),
                    ]
                )
        self.stdout.write(self.style.SUCCESS(f"\nСписок без фото выгружен: {path} ({len(empty)} строк)"))

    def _probe(self, external) -> dict[int, str]:
        """Опрос внешних ссылок. Ошибка сети — не повод падать, пишем её как статус."""
        import requests

        statuses: dict[int, str] = {}
        for pk, _title, url in external:
            try:
                resp = requests.head(url, timeout=_TIMEOUT, allow_redirects=True)
                # часть хостов не отвечает на HEAD — переспрашиваем GET'ом
                if resp.status_code >= 400:
                    resp = requests.get(url, timeout=_TIMEOUT, stream=True)
                statuses[pk] = str(resp.status_code)
            except Exception as exc:  # noqa: BLE001 — интересен сам факт недоступности
                statuses[pk] = type(exc).__name__
        return statuses
