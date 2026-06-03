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
    ShoppingListAccessSerializer,
    ShoppingListBriefSerializer,
    ShoppingListItemSerializer,
    ShoppingListItemWriteSerializer,
    ShoppingListSerializer,
)
from .services import build_items_from_menu, parse_csv, parse_text_with_ai


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
        shared = Q(accesses__user=user)
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
        bulk = [
            ShoppingListItem(
                shopping_list=sl,
                name=d["name"],
                quantity=d.get("quantity"),
                unit=d.get("unit") or "",
                category=d.get("category") or "",
                sort_order=i,
            )
            for i, d in enumerate(items_data)
        ]
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
        ser = ShoppingListItemWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = ShoppingListItem.objects.create(shopping_list=sl, **ser.validated_data)
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
            PurchaseHistoryEntry.objects.create(
                family=sl.family,
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                category=item.category,
                purchased_by=request.user,
                source_list_id=sl.id,
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
        acc, _ = ShoppingListAccess.objects.update_or_create(
            shopping_list=sl,
            user=target,
            defaults={
                "can_read": True,
                "can_toggle": ser.validated_data["can_toggle"],
                "can_export": ser.validated_data["can_export"],
            },
        )
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
        items = ShoppingListItem.objects.filter(shopping_list=sl)
        by_cat = {}
        for it in items:
            by_cat.setdefault(it.category or "", []).append(
                {
                    "name": it.name,
                    "quantity": str(it.quantity) if it.quantity is not None else None,
                    "unit": it.unit,
                    "is_purchased": it.is_purchased,
                }
            )
        return Response(
            {
                "title": sl.name,
                "created_at": sl.created_at,
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
        entry = PurchaseHistoryEntry.objects.create(
            family=family,
            name=name,
            quantity=request.data.get("quantity"),
            unit=request.data.get("unit") or "",
            category=request.data.get("category") or "",
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
