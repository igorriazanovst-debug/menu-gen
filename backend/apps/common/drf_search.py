"""MG_YOSEARCH: фильтр поиска DRF, не различающий «е» и «ё».

Вынесен из apps/common/search.py, чтобы тот не тянул rest_framework: search.py
подключается в admin.py, а он импортируется при старте Django — до того, как
тесты успевают переопределить настройки DRF.
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef
from rest_framework.filters import SearchFilter

from .search import yo_search_q

class YoSearchFilter(SearchFilter):
    """SearchFilter из DRF, не различающий «е» и «ё».

    Слова запроса, как и в оригинале, объединяются по И: «борщ красный» найдёт
    только то, где встречаются оба.
    """

    def filter_queryset(self, request, queryset, view):
        search_fields = self.get_search_fields(view, request)
        terms = self.get_search_terms(request)
        if not search_fields or not terms:
            return queryset

        # Префиксы DRF (^ = @ $) меняют тип поиска — в таком случае отдаём
        # работу базовой реализации, чтобы не терять её семантику.
        if any(field[0] in self.lookup_prefixes for field in search_fields):
            return super().filter_queryset(request, queryset, view)

        base = queryset
        for term in terms:
            queryset = queryset.filter(yo_search_q(queryset.model, search_fields, term))

        if self.must_call_distinct(queryset, search_fields):
            # Тот же приём, что в самом DRF: точнее distinct() на M2M и
            # одинаково работает во всех СУБД.
            queryset = base.filter(Exists(queryset.filter(pk=OuterRef("pk"))))
        return queryset
