"""MG_SALES: сводка над списком в админке.

Список платежей отвечает на вопрос «кто и что купил», но не на вопрос
«сколько всего». Считать строки глазами — то, ради чего раздел и заводят.

Сводка считается по ТЕКУЩЕМУ ОТБОРУ, а не по всей таблице. Это важнее, чем
кажется: иначе фильтр по месяцу менял бы список, но не числа над ним, и два
разных ответа на одной странице спорили бы между собой. Поставили фильтр
«оплачено в ноябре» — и сводка про ноябрь.
"""


def money(value) -> str:
    """Сумма для показа: «12 345 ₽», без копеек и с пробелом между тысячами.

    Копейки в сводке только мешают: решения принимают по порядку величины, а
    точные суммы сверяют в ЮKassa, а не здесь. Разряды разделяются узким
    неразрывным пробелом — обычный даёт перенос числа по строке.

    Пишется руками, а не через `intcomma`: `django.contrib.humanize` в проекте
    не подключён, и тянуть приложение ради одной запятой незачем.
    """
    return f"{int(value or 0):,}".replace(",", " ") + " ₽"


def count(value) -> str:
    """То же разделение разрядов, но без валюты."""
    return f"{int(value or 0):,}".replace(",", " ")


class SalesSummaryMixin:
    """Добавляет блок чисел над списком. Наследник задаёт `summary_rows`.

    `summary_rows(queryset)` возвращает список пар (подпись, значение). Пустой
    список означает «показывать нечего» — блок не рисуется вовсе, и пустая
    рамка над пустым списком не появляется.
    """

    change_list_template = "admin/common/change_list_with_summary.html"

    def summary_rows(self, queryset):  # pragma: no cover - переопределяется
        return []

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        # Невалидный фильтр, редирект, экспорт — у таких ответов контекста нет,
        # и лезть в него значит уронить страницу вместо показа ошибки.
        cl = getattr(response, "context_data", {}).get("cl") if hasattr(response, "context_data") else None
        if cl is not None:
            response.context_data["sales_summary"] = self.summary_rows(cl.queryset)
        return response
