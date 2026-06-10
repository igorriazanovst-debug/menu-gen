# MG_SHOP001_views
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.menu.models import Menu

from .models import PurchaseHistoryEntry, ShoppingList, ShoppingListAccess, ShoppingListItem
from .permissions import access_level, get_user_family, is_family_head
from .serializers import (
    CreateListSerializer,
    GrantAccessSerializer,
    PurchaseHistoryEntrySerializer,
    PendingSharedListSerializer,  # MG_SHAREACCEPT
    ShoppingListAccessSerializer,
    ShoppingListBriefSerializer,
    ShoppingListItemSerializer,
    ShoppingListItemWriteSerializer,
    ShoppingListSerializer,
)

# MG_RUBRIC002_views_import
from .services import (
    build_items_from_menu,
    classify_new_product,
    ensure_product,
    parse_csv,
    parse_text_with_ai,
    search_rubric,
)


def _annotate(qs):
    return qs.annotate(
        items_total=Count("items"),
        items_purchased=Count("items", filter=Q(items__is_purchased=True)),
    )


def _get_list_for_user(user, list_id):
    """Return (shopping_list, caps) or (None, None) if no access."""
    try:
        sl = ShoppingList.objects.select_related("family").get(id=list_id)
    except ShoppingList.DoesNotExist:
        return None, None
    caps = access_level(user, sl)
    return (sl, caps) if caps and caps["read"] else (None, None)


class ShoppingListsView(APIView):
    """GET list (own + shared), POST create (1.1/1.2/1.3)."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ShoppingListBriefSerializer(many=True)})
    def get(self, request):
        user = request.user
        family = get_user_family(user)
        archived = request.query_params.get("archived") == "true"

        own = Q(family=family) if family else Q(pk__in=[])
        # MG_SHAREACCEPT: only ACCEPTED external shares show in the main list.
        shared = Q(accesses__user=user, accesses__status=ShoppingListAccess.Status.ACCEPTED)
        qs = ShoppingList.objects.filter(own | shared, is_archived=archived).distinct()
        qs = _annotate(qs)
        return Response(ShoppingListBriefSerializer(qs, many=True).data)

    @extend_schema(request=CreateListSerializer, responses={201: ShoppingListSerializer})
    def post(self, request):
        user = request.user
        family = get_user_family(user)
        if not family:
            return Response({"detail": "Нет семьи."}, status=status.HTTP_400_BAD_REQUEST)
        if not is_family_head(user, family):
            return Response({"detail": "Только глава семьи."}, status=status.HTTP_403_FORBIDDEN)

        ser = CreateListSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        src = data["source"]

        menu = None
        items_data = []
        if src in (ShoppingList.Source.MENU, ShoppingList.Source.FRIDGE):
            try:
                menu = Menu.objects.get(id=data["menu_id"], family=family)
            except Menu.DoesNotExist:
                return Response({"detail": "Меню не найдено."}, status=status.HTTP_404_NOT_FOUND)
            # MG_RECIPELINK_VIEW_A: build uses precomputed product links (category + qty);
            # AI cleanup happens inside build only for link-less recipes.
            items_data = build_items_from_menu(menu, family, subtract_fridge=(src == ShoppingList.Source.FRIDGE))
        elif src == ShoppingList.Source.AI_TEXT:
            items_data = parse_text_with_ai(data["text"])
            if items_data is None:
                return Response({"detail": "ИИ не смог разобрать текст."}, status=status.HTTP_502_BAD_GATEWAY)
        elif src == ShoppingList.Source.CSV:
            items_data = parse_csv(data["csv_text"])

        sl = ShoppingList.objects.create(
            family=family,
            name=data["name"],
            source=src,
            created_by=user,
            menu=menu,
        )
        # MG_IMPORTTRUNC: clamp to column max_length so a long ingredient
        # name (>255) does not 500 the whole import.
        # MG_RECIPELINK_VIEW_B: set category cache string + FK + product FK so the
        # imported list is grouped/coloured by section.
        from apps.fridge.models import ProductCategory
        _cat_name = {c.id: c.name_ru for c in ProductCategory.objects.all()}

        def _mx(f):
            return ShoppingListItem._meta.get_field(f).max_length
        _nm, _un, _ct = _mx("name"), _mx("unit"), _mx("category")
        bulk = []
        for i, d in enumerate(items_data):
            _cid = d.get("category_fk_id")
            _cstr = d.get("category") or _cat_name.get(_cid, "")
            bulk.append(
                ShoppingListItem(
                    shopping_list=sl,
                    name=(d["name"] or "")[:_nm],
                    quantity=d.get("quantity"),
                    unit=(d.get("unit") or "")[:_un],
                    category=(_cstr or "")[:_ct],
                    category_fk_id=_cid,
                    product_id=d.get("product_id"),
                    sort_order=i,
                )
            )
        if bulk:
            ShoppingListItem.objects.bulk_create(bulk)

        sl = _annotate(ShoppingList.objects.filter(id=sl.id)).first()
        return Response(ShoppingListSerializer(sl).data, status=status.HTTP_201_CREATED)


class ShoppingListDetailView(APIView):
    """GET detail, PATCH rename/archive, DELETE (1, 2, 6-archive)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, list_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        sl = _annotate(ShoppingList.objects.filter(id=sl.id)).first()
        out = ShoppingListSerializer(sl).data
        out["capabilities"] = caps
        return Response(out)

    def patch(self, request, list_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["manage"]:
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get("name")
        if name is not None:
            sl.name = name
        archived = request.data.get("is_archived")
        if archived is not None:
            sl.is_archived = bool(archived)
            sl.archived_at = timezone.now() if sl.is_archived else None
        sl.save()
        sl = _annotate(ShoppingList.objects.filter(id=sl.id)).first()
        return Response(ShoppingListSerializer(sl).data)

    def delete(self, request, list_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["manage"]:
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)
        sl.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShoppingItemsView(APIView):
    """POST add item, used for manual editing (2)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, list_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["manage"]:
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)
        # MG_RUBRIC002: resolve / create the rubricator product, set FK + cached fields.
        ser = ShoppingListItemWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        category_slug = data.pop("category_slug", "")
        product_id = data.pop("product_id", None)
        from apps.fridge.models import Product, ProductCategory

        product = None
        if product_id:
            product = Product.objects.select_related("category_fk").filter(id=product_id).first()
        if product is None:
            product = ensure_product(
                data.get("name", ""),
                category_slug=category_slug,
                unit=data.get("unit", ""),
            )
        cat = product.category_fk if product else None
        if cat is None and category_slug:
            cat = ProductCategory.objects.filter(slug=category_slug).first()
        # MG_RUBRIC006_prefill: provided price, else product's last known price.
        price = data.get("price_per_unit")
        if price is None and product is not None:
            price = product.last_price
        item = ShoppingListItem.objects.create(
            shopping_list=sl,
            product=product,
            legacy_product_id=(product.id if product else None),
            price_per_unit=price,
            category_fk=cat,
            category=(cat.name_ru if cat else data.get("category", "")),
            name=data.get("name", ""),
            quantity=data.get("quantity"),
            unit=data.get("unit") or (product.default_unit if product else ""),
            sort_order=data.get("sort_order", 0),
        )
        return Response(ShoppingListItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ShoppingItemDetailView(APIView):
    """PATCH edit item, DELETE item (2)."""

    permission_classes = [permissions.IsAuthenticated]

    def _get(self, user, list_id, item_id):
        sl, caps = _get_list_for_user(user, list_id)
        if not sl:
            return None, None, None
        try:
            item = ShoppingListItem.objects.get(id=item_id, shopping_list=sl)
        except ShoppingListItem.DoesNotExist:
            return sl, caps, None
        return sl, caps, item

    def patch(self, request, list_id, item_id):
        sl, caps, item = self._get(request.user, list_id, item_id)
        if not sl or not item:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["manage"]:
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)
        ser = ShoppingListItemWriteSerializer(item, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ShoppingListItemSerializer(item).data)

    def delete(self, request, list_id, item_id):
        sl, caps, item = self._get(request.user, list_id, item_id)
        if not sl or not item:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["manage"]:
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShoppingItemToggleView(APIView):
    """PATCH toggle purchased — needs can_toggle (3.2). Logs history (6)."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, list_id, item_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["toggle"]:
            return Response({"detail": "Нет прав на отметку."}, status=status.HTTP_403_FORBIDDEN)
        try:
            item = ShoppingListItem.objects.get(id=item_id, shopping_list=sl)
        except ShoppingListItem.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        new_val = request.data.get("is_purchased")
        item.is_purchased = (not item.is_purchased) if new_val is None else bool(new_val)
        if item.is_purchased:
            item.purchased_by = request.user
            item.purchased_at = timezone.now()
            # MG_RUBRIC006_toggle_price
            PurchaseHistoryEntry.objects.create(
                family=sl.family,
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                category=item.category,
                price_per_unit=item.price_per_unit,
                purchased_by=request.user,
                source_list_id=sl.id,
            )
            if item.price_per_unit is not None and item.product_id:
                from apps.fridge.models import Product

                Product.objects.filter(id=item.product_id).update(
                    last_price=item.price_per_unit, last_price_at=timezone.now()
                )
        else:
            item.purchased_by = None
            item.purchased_at = None
        item.save()
        return Response(ShoppingListItemSerializer(item).data)


class ShoppingListAccessView(APIView):
    """GET accesses, POST grant, DELETE revoke (3.1/3.2/3.3)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, list_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["manage"]:
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)
        qs = ShoppingListAccess.objects.filter(shopping_list=sl).select_related("user")
        return Response(ShoppingListAccessSerializer(qs, many=True).data)

    def post(self, request, list_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["manage"]:
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)
        ser = GrantAccessSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        target = ser.resolve_user()
        # MG_SHAREACCEPT: new grant starts PENDING (recipient must accept).
        acc, created = ShoppingListAccess.objects.get_or_create(
            shopping_list=sl,
            user=target,
            defaults={
                "can_read": True,
                "can_toggle": ser.validated_data["can_toggle"],
                "can_export": ser.validated_data["can_export"],
                "status": ShoppingListAccess.Status.PENDING,
            },
        )
        if not created:
            acc.can_read = True
            acc.can_toggle = ser.validated_data["can_toggle"]
            acc.can_export = ser.validated_data["can_export"]
            # Re-granting a previously rejected share re-issues it as pending.
            if acc.status == ShoppingListAccess.Status.REJECTED:
                acc.status = ShoppingListAccess.Status.PENDING
                acc.responded_at = None
            acc.save()
        return Response(ShoppingListAccessSerializer(acc).data, status=status.HTTP_201_CREATED)

    def delete(self, request, list_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["manage"]:
            return Response({"detail": "Нет прав."}, status=status.HTTP_403_FORBIDDEN)
        access_id = request.data.get("access_id") or request.query_params.get("access_id")
        if not access_id:
            return Response({"detail": "access_id обязателен."}, status=status.HTTP_400_BAD_REQUEST)
        ShoppingListAccess.objects.filter(id=access_id, shopping_list=sl).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShoppingListExportView(APIView):
    """GET structured data for client-side print/PDF (5). Needs can_export."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, list_id):
        sl, caps = _get_list_for_user(request.user, list_id)
        if not sl:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not caps["export"]:
            return Response({"detail": "Нет прав на экспорт."}, status=status.HTTP_403_FORBIDDEN)
        # MG_RUBRIC006_export
        from decimal import Decimal, ROUND_HALF_UP  # MG_SHOPBUG_BE

        items = ShoppingListItem.objects.filter(shopping_list=sl)
        by_cat = {}
        grand = Decimal(0)
        any_price = False
        for it in items:
            line = None
            if it.price_per_unit is not None:
                any_price = True
                qty = it.quantity if it.quantity is not None else 1
                # MG_SHOPBUG_BE: quantize line.
                line = (it.price_per_unit * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                grand += line
            by_cat.setdefault(it.category or "", []).append(
                {
                    "name": it.name,
                    "quantity": str(it.quantity) if it.quantity is not None else None,
                    "unit": it.unit,
                    "price_per_unit": str(it.price_per_unit) if it.price_per_unit is not None else None,
                    "line_total": str(line) if line is not None else None,
                    "is_purchased": it.is_purchased,
                }
            )
        return Response(
            {
                "title": sl.name,
                "created_at": sl.created_at,
                "currency": sl.family.currency,
                # MG_SHOPBUG_BE
                "total_price": str(grand.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if any_price else None,
                "categories": [{"category": cat, "items": its} for cat, its in by_cat.items()],
            }
        )


class PurchaseHistoryView(APIView):
    """GET history log, POST add manual entry, DELETE entry (6.1)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        family = get_user_family(request.user)
        if not family:
            return Response([])
        qs = PurchaseHistoryEntry.objects.filter(family=family).select_related("purchased_by")
        return Response(PurchaseHistoryEntrySerializer(qs, many=True).data)

    def post(self, request):
        family = get_user_family(request.user)
        if not family:
            return Response({"detail": "Нет семьи."}, status=status.HTTP_400_BAD_REQUEST)
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "name обязателен."}, status=status.HTTP_400_BAD_REQUEST)
        # MG_RUBRIC006_history_post
        entry = PurchaseHistoryEntry.objects.create(
            family=family,
            name=name,
            quantity=request.data.get("quantity"),
            unit=request.data.get("unit") or "",
            category=request.data.get("category") or "",
            price_per_unit=request.data.get("price_per_unit"),
            purchased_by=request.user,
            source_list_id=request.data.get("source_list_id"),
        )
        return Response(PurchaseHistoryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        family = get_user_family(request.user)
        entry_id = request.data.get("entry_id") or request.query_params.get("entry_id")
        if not entry_id:
            return Response({"detail": "entry_id обязателен."}, status=status.HTTP_400_BAD_REQUEST)
        PurchaseHistoryEntry.objects.filter(id=entry_id, family=family).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── MG_RUBRIC002: rubricator endpoints ──────────────────────────────────────
class RubricSearchView(APIView):
    """GET /shopping/rubric/search/?q=<text>

    Searches the shared Product rubricator. If matches exist, returns them.
    If none and ?classify=1, returns an AI-suggested category for a NEW product
    so the client can pre-fill (user may override before adding).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        q = request.query_params.get("q", "")
        results = search_rubric(q)
        payload = {"query": q, "results": results, "suggestion": None}
        if not results and request.query_params.get("classify") in ("1", "true") and q.strip():
            payload["suggestion"] = classify_new_product(q.strip())
        return Response(payload)


# ── MG_SHAREACCEPT: pending shares (accept / reject) ─────────────────────────
class PendingSharedListsView(APIView):
    """GET lists shared TO me that await my accept/reject."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = (
            ShoppingList.objects.filter(
                accesses__user=request.user,
                accesses__status=ShoppingListAccess.Status.PENDING,
                is_archived=False,
            )
            .distinct()
            .prefetch_related("accesses")
        )
        qs = _annotate(qs)
        ser = PendingSharedListSerializer(qs, many=True, context={"user": request.user})
        return Response(ser.data)


class SharedAccessRespondView(APIView):
    """POST {"action": "accept"|"reject"} for the current user's pending share."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, list_id):
        action = (request.data.get("action") or "").lower()
        if action not in ("accept", "reject"):
            return Response(
                {"detail": "action должен быть accept или reject."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        acc = ShoppingListAccess.objects.filter(shopping_list_id=list_id, user=request.user).first()
        if not acc:
            return Response(status=status.HTTP_404_NOT_FOUND)
        acc.status = (
            ShoppingListAccess.Status.ACCEPTED
            if action == "accept"
            else ShoppingListAccess.Status.REJECTED
        )
        acc.responded_at = timezone.now()
        acc.save(update_fields=["status", "responded_at"])
        return Response(ShoppingListAccessSerializer(acc).data)


# MG_RUBRICBROWSE: browse rubricator (IsAuthenticated, no premium gate)
class RubricCategoriesView(APIView):
    """GET /shopping/rubric/categories/ - active categories for the browse picker."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .services import list_rubric_categories

        return Response(list_rubric_categories())


class RubricBrowseView(APIView):
    """GET /shopping/rubric/browse/?category=<slug> - products in a category."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .services import browse_rubric

        slug = request.query_params.get("category", "")
        return Response({"category": slug, "results": browse_rubric(slug)})
