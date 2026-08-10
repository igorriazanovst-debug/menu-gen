"""MG_YOSEARCH / MG_MORPHSEARCH: поиск, терпимый к написанию и словоформам.

Две вещи мешали поиску находить очевидное:

1. «ё». В русских текстах её пишут непоследовательно: в базе «Свёкла тёртая», а
   набирают «свекла тертая» — и ничего не находится. Обратное тоже верно.
2. Окончания. Сравнивались подстроки, поэтому «тушеная» не находила «тушенную»,
   «яйца» — «яйцо», «супы» — «суп».

Обе буквы считаются одной, а от слова из запроса берётся основа (см.
morphology.ru_stem) — она является началом слова в любой его форме, поэтому
поиск подстроки находит все формы сразу. Данные в базе при этом не меняются и
никаких индексов не требуется.

Реализовано регулярным выражением: «е»/«ё» превращаются в класс ``[её]``. Это
работает и в Postgres, и в SQLite (Django регистрирует для него функцию REGEXP).
Границы слов (``\\m``/``\\b``) не используются намеренно — они пишутся
по-разному в Postgres и в Python.

Нетекстовым полям (например, JSONField с категориями) регулярное выражение не
достаётся: для них остаётся обычный ``icontains``. Такие поля в поиске
второстепенны, а поведение lookup'ов у них зависит от СУБД — рисковать незачем.

DRF-фильтр вынесен в соседний модуль drf_search: этот модуль подключается в
admin.py, который Django импортирует при старте — раньше, чем тесты успевают
настроить DRF. Лишний импорт rest_framework оттуда фиксировал настройки DRF
слишком рано и включал троттлинг в тестах.

Тот же приём с «ё» уже применяется в проекте точечно: apps/fridge/aliases.py,
apps/common/allergens.py, apps/recipes/recipe_products.py приводят «ё» к «е»
перед сравнением.
"""

from __future__ import annotations

import re

from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, Q, TextField
from django.db.models.constants import LOOKUP_SEP

from .morphology import stem_prefix

# Поля, по которым осмысленно искать регулярным выражением.
TEXT_FIELDS = (CharField, TextField)


def normalize_yo(text: str) -> str:
    """«ё» → «е» для сравнений на стороне Python."""
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def _yo_class(text: str) -> str:
    """Экранированный текст, где «е» и «ё» взаимозаменяемы."""
    return re.sub(r"[еёЕЁ]", "[её]", re.escape(text))


def search_regex(term: str) -> str:
    """Запрос → регулярное выражение: основа слова, «е» и «ё» равны.

    Спецсимволы экранируются: пользователь может ввести «(» или «*», и запрос
    не должен превращаться в сломанное или неожиданно широкое выражение.
    Слова фразы разделяются ``\\s+`` — каждое сокращается до основы отдельно,
    иначе окончание отсеклось бы только у последнего.
    """
    words = (term or "").split()
    if not words:
        return _yo_class(term or "")
    return r"\s+".join(_yo_class(stem_prefix(w)) for w in words)


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


def search_condition(model, path: str, term: str) -> Q:
    """Условие поиска по одному полю: regex для текста, icontains для прочего."""
    field = _resolve_field(model, path)
    if isinstance(field, TEXT_FIELDS):
        return Q(**{f"{path}__iregex": search_regex(term)})
    return Q(**{f"{path}__icontains": term})


def search_q(model, paths, term: str) -> Q:
    """ИЛИ по всем полям для одного слова запроса."""
    condition = Q()
    for path in paths:
        condition |= search_condition(model, path, term)
    return condition


class AdminSearchMixin:
    """Тот же поиск для списков Django-админки.

    Подмешивается к ModelAdmin: ``class RecipeAdmin(AdminSearchMixin, ModelAdmin)``.
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
            queryset = queryset.filter(search_q(queryset.model, search_fields, word))
        # Поиск по связанным полям может дублировать строки — админка сама
        # добавит distinct(), если вернуть True.
        may_have_duplicates = any(LOOKUP_SEP in field for field in search_fields)
        return queryset, may_have_duplicates
