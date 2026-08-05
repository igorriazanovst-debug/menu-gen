"""MG_YOSEARCH: поиск, не различающий «е» и «ё».

В русских текстах «ё» пишут непоследовательно: в базе может лежать «Свёкла
тёртая», а пользователь наберёт «свекла тертая» — и не найдёт ничего. Обратное
тоже верно. Поэтому в поиске обе буквы считаются одной.

Реализовано регулярным выражением: каждая «е» или «ё» в запросе превращается в
класс ``[её]``. Это работает и в Postgres, и в SQLite (Django регистрирует для
него функцию REGEXP), не требует денормализованных колонок и индексов и не
меняет данные.

Нетекстовым полям (например, JSONField с категориями) регулярное выражение не
достаётся: для них остаётся обычный ``icontains``. Такие поля в поиске
второстепенны, а поведение lookup'ов у них зависит от СУБД — рисковать незачем.

DRF-фильтр вынесен в соседний модуль drf_search: этот модуль подключается в
admin.py, который Django импортирует при старте — раньше, чем тесты успевают
настроить DRF. Лишний импорт rest_framework оттуда фиксировал настройки DRF
слишком рано и включал троттлинг в тестах.

Тот же приём уже применяется в проекте точечно: apps/fridge/aliases.py,
apps/common/allergens.py, apps/recipes/recipe_products.py приводят «ё» к «е»
перед сравнением.
"""

from __future__ import annotations

import re

from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, Q, TextField
from django.db.models.constants import LOOKUP_SEP

# Поля, по которым осмысленно искать регулярным выражением.
TEXT_FIELDS = (CharField, TextField)


def normalize_yo(text: str) -> str:
    """«ё» → «е» для сравнений на стороне Python."""
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def yo_regex(term: str) -> str:
    """Запрос → регулярное выражение, где «е» и «ё» взаимозаменяемы.

    Спецсимволы экранируются: пользователь может ввести «(» или «*», и запрос
    не должен превращаться в сломанное или неожиданно широкое выражение.
    """
    escaped = re.escape(term or "")
    # re.escape экранирует и кириллицу в старых версиях Python — здесь нет, но
    # подстановку делаем по конкретным буквам, поэтому это безопасно.
    return re.sub(r"[еёЕЁ]", "[её]", escaped)


def _resolve_field(model, path: str):
    """Последнее поле по пути вида ``owner__email``. None — если не нашли."""
    opts = model._meta
    field = None
    for part in path.split(LOOKUP_SEP):
        try:
            field = opts.get_field(part)
        except FieldDoesNotExist:
            return None
        if hasattr(field, "path_infos"):
            opts = field.path_infos[-1].to_opts
    return field


def yo_condition(model, path: str, term: str) -> Q:
    """Условие поиска по одному полю: regex для текста, icontains для прочего."""
    field = _resolve_field(model, path)
    if isinstance(field, TEXT_FIELDS):
        return Q(**{f"{path}__iregex": yo_regex(term)})
    return Q(**{f"{path}__icontains": term})


def yo_search_q(model, paths, term: str) -> Q:
    """ИЛИ по всем полям для одного слова запроса."""
    condition = Q()
    for path in paths:
        condition |= yo_condition(model, path, term)
    return condition


class YoAdminSearchMixin:
    """Тот же поиск для списков Django-админки.

    Подмешивается к ModelAdmin: ``class RecipeAdmin(YoAdminSearchMixin, ModelAdmin)``.
    """

    def get_search_results(self, request, queryset, search_term):
        search_fields = self.get_search_fields(request)
        term = (search_term or "").strip()
        if not search_fields or not term:
            return super().get_search_results(request, queryset, search_term)

        # Префиксы Django (^ = @) — отдаём базовой реализации.
        if any(field[0] in ("^", "=", "@") for field in search_fields):
            return super().get_search_results(request, queryset, search_term)

        for word in term.split():
            queryset = queryset.filter(yo_search_q(queryset.model, search_fields, word))
        # Поиск по связанным полям может дублировать строки — админка сама
        # добавит distinct(), если вернуть True.
        may_have_duplicates = any(LOOKUP_SEP in field for field in search_fields)
        return queryset, may_have_duplicates
