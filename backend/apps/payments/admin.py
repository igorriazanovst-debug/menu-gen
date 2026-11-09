"""MG_SALES: продажи подписок через ЮKassa.

Раздел отвечает на три вопроса сразу: сколько купили, кто купил и на какой
срок. До этого список платежей показывал семью, сумму и статус — по нему
нельзя было ни написать человеку, ни понять, что именно он оплатил.

Промокоды сюда не попадают намеренно: это выдача, а не продажа через кассу, и
считать их вместе значит потерять разницу между деньгами и подарками. Они
живут отдельным разделом — «Активации промокодов».
"""

from django.contrib import admin
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils.html import format_html

from apps.common.admin_summary import SalesSummaryMixin, count, money

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(SalesSummaryMixin, admin.ModelAdmin):
    list_display = (
        "paid_at",
        "status",
        "customer",
        "phone",
        "family_size",
        "term",
        "amount_rub",
        "purchase_no",
        "provider",
    )
    list_filter = ("status", "provider", "paid_at", "offer")
    search_fields = (
        "family__name",
        "family__owner__email",
        "family__owner__name",
        "family__owner__phone",
        "payment_id",
    )
    date_hierarchy = "paid_at"
    raw_id_fields = ("family", "subscription", "offer")
    readonly_fields = ("payment_id", "created_at")
    ordering = ("-paid_at", "-created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Без select_related каждая строка списка тянула бы семью, владельца и
        # оффер отдельными запросами — сотня строк превращается в четыре сотни.
        qs = qs.select_related("family", "family__owner", "offer", "subscription")
        # Какая по счёту это покупка у семьи. Считается подзапросом, а не
        # оконной функцией: оконная считалась бы ПОСЛЕ фильтра, и у платежа с
        # фильтром «ноябрь» номер был бы «первый» вместо «третьей покупки».
        earlier = (
            Payment.objects.filter(
                family_id=OuterRef("family_id"),
                status=Payment.Status.SUCCEEDED,
                paid_at__lte=OuterRef("paid_at"),
            )
            .order_by()
            .values("family_id")
            .annotate(n=Count("id"))
            .values("n")
        )
        return qs.annotate(
            members_count=Count("family__members", distinct=True),
            purchase_index=Coalesce(Subquery(earlier, output_field=IntegerField()), 0),
        )

    # ── колонки ──────────────────────────────────────────────────────────────

    @admin.display(description="Клиент", ordering="family__owner__email")
    def customer(self, obj):
        owner = getattr(obj.family, "owner", None) if obj.family else None
        if owner is None:
            # Семью могли удалить: платёж это переживает намеренно (MG_ACCDEL).
            return "— семья удалена —"
        name = owner.name or "без имени"
        contact = owner.email or owner.phone or f"id {owner.pk}"
        return format_html("{}<br><span style='opacity:.7'>{}</span>", name, contact)

    @admin.display(description="Телефон")
    def phone(self, obj):
        owner = getattr(obj.family, "owner", None) if obj.family else None
        return (owner.phone if owner else None) or "—"

    @admin.display(description="В семье", ordering="members_count")
    def family_size(self, obj):
        if obj.family is None:
            return "—"
        return obj.members_count

    @admin.display(description="Срок")
    def term(self, obj):
        """На сколько купили.

        У старых платежей оффера нет вовсе — тогда срок берётся из самой
        подписки. Выдумывать «месяц по умолчанию» нельзя: годовую покупку это
        показало бы как месячную.
        """
        if obj.offer_id and obj.offer:
            return f"{obj.offer.months} мес · {obj.offer.title}"
        sub = obj.subscription
        if sub and sub.started_at and sub.expires_at:
            days = (sub.expires_at - sub.started_at).days
            return f"≈{max(1, round(days / 30))} мес (из подписки)"
        return "—"

    @admin.display(description="Сумма", ordering="amount")
    def amount_rub(self, obj):
        return f"{obj.amount} {obj.currency}"

    @admin.display(description="Покупка №", ordering="purchase_index")
    def purchase_no(self, obj):
        """Которая по счёту покупка этой семьи — видно, кто продлевается."""
        if obj.status != Payment.Status.SUCCEEDED:
            return "—"
        return obj.purchase_index or "—"

    # ── сводка ───────────────────────────────────────────────────────────────

    def summary_rows(self, queryset):
        # Считаем по чистому набору тех же строк, а не по списочному: у того
        # навешены аннотации с GROUP BY, и агрегат поверх группировки даёт
        # запрос, который легко прочитать неверно.
        rows_qs = Payment.objects.filter(pk__in=queryset.values("pk"))
        agg = rows_qs.aggregate(
            sold=Count("id", filter=Q(status=Payment.Status.SUCCEEDED)),
            revenue=Sum("amount", filter=Q(status=Payment.Status.SUCCEEDED)),
            refunded=Count("id", filter=Q(status=Payment.Status.REFUNDED)),
            refunded_sum=Sum("amount", filter=Q(status=Payment.Status.REFUNDED)),
            pending=Count("id", filter=Q(status=Payment.Status.PENDING)),
            buyers=Count("family_id", filter=Q(status=Payment.Status.SUCCEEDED), distinct=True),
            months=Sum("offer__months", filter=Q(status=Payment.Status.SUCCEEDED)),
        )
        sold = agg["sold"] or 0
        buyers = agg["buyers"] or 0
        rows = [
            ("Куплено подписок", count(sold)),
            ("Выручка", money(agg["revenue"])),
            ("Покупателей", count(buyers)),
        ]
        if buyers:
            # Больше единицы означает, что люди продлеваются, — это и есть
            # главный признак живого продукта.
            rows.append(("Покупок на покупателя", f"{sold / buyers:.2f}".replace(".", ",")))
        if agg["months"]:
            rows.append(("Продано месяцев", count(agg["months"])))
        if agg["refunded"]:
            rows.append(("Возвраты", f"{count(agg['refunded'])} на {money(agg['refunded_sum'])}"))
        if agg["pending"]:
            rows.append(("Ждут оплаты", count(agg["pending"])))
        return rows
