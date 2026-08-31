"""MG_ACCDEL: ручки удаления аккаунта.

Два входа, оба обязательны по требованиям Google Play:

  * из приложения — POST /users/me/delete/ с подтверждением паролем;
  * без входа, по публичному веб-адресу — /auth/account-deletion/request/ и
    .../confirm/. Подтверждение письмом, потому что иначе форма без входа
    позволяла бы удалить чужой аккаунт, зная только e-mail.
"""

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User

from .account_deletion import GRACE_DAYS, _pick_heir, read_token, request_deletion, send_confirmation_email


def _consequences(user) -> dict:
    """Что именно произойдёт — чтобы экран подтверждения не врал абстракциями.

    Пользователю важно ровно одно различие: уедут ли вместе с ним меню,
    холодильник и дневники всей семьи или семья останется жить без него.
    """
    from apps.family.models import Family

    owned = Family.objects.filter(owner=user)
    families_lost = []
    heir_names = []
    for family in owned:
        heir_id = _pick_heir(family, leaving=user)
        if heir_id:
            heir = User.objects.filter(id=heir_id).first()
            heir_names.append(heir.name or str(heir) if heir else "")
        else:
            families_lost.append(family.name or "Моя семья")
    # MG_ACCDEL: оплаченная подписка сгорает без возврата — так написано в
    # оферте (п. 18.5: прекращение использования не основание для возврата за
    # уже оплаченный период). Молчать об этом на экране подтверждения нельзя:
    # человек удаляет аккаунт, не зная, что вместе с ним теряет оплаченное, и
    # узнаёт об этом уже необратимо.
    paid_until = None
    family = _family_of(user)
    if family is not None:
        from apps.subscriptions.models import Subscription
        from apps.subscriptions.permissions import PREMIUM_ACTIVE_STATUSES, PREMIUM_PLAN_CODE

        sub = (
            Subscription.objects.filter(
                family=family,
                plan__code=PREMIUM_PLAN_CODE,
                status__in=PREMIUM_ACTIVE_STATUSES,
                expires_at__gt=timezone.now(),
            )
            .order_by("-expires_at")
            .first()
        )
        paid_until = sub.expires_at if sub else None

    return {
        "grace_days": GRACE_DAYS,
        "family_data_will_be_deleted": bool(families_lost),
        "families_to_delete": families_lost,
        "new_owners": heir_names,
        "subscription_paid_until": paid_until,
    }


def _family_of(user):
    """Семья пользователя: своя или та, в которой он состоит."""
    from apps.family.models import Family, FamilyMember

    own = Family.objects.filter(owner=user).first()
    if own:
        return own
    membership = FamilyMember.objects.select_related("family").filter(user=user).first()
    return membership.family if membership else None


class AccountDeleteView(APIView):
    """GET — что будет удалено; POST — запросить удаление."""

    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(responses={200: None})
    def get(self, request):
        return Response(_consequences(request.user))

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        user = request.user
        # Пароль спрашиваем у всех, у кого он есть: чужой разблокированный
        # телефон не должен уметь стереть аккаунт одним нажатием. У аккаунтов
        # без пароля (VK, управляемые) спрашивать нечего — они дошли сюда по
        # действующему токену.
        if user.has_usable_password():
            password = request.data.get("password") or ""
            if not user.check_password(password):
                return Response(
                    {"detail": "Неверный пароль.", "code": "invalid_password"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        purge_at = request_deletion(user)
        return Response(
            {
                "detail": (
                    f"Аккаунт заблокирован, данные будут удалены через {GRACE_DAYS} дней. "
                    f"Чтобы отменить удаление, войдите в приложение до этого срока."
                ),
                "grace_days": GRACE_DAYS,
                "purge_after": purge_at,
            }
        )


class PublicDeletionRequestView(APIView):
    """POST /auth/account-deletion/request/ {email} — письмо со ссылкой.

    Ответ одинаков независимо от того, нашёлся аккаунт или нет: иначе форма
    превратилась бы в проверку «зарегистрирован ли такой e-mail», доступную
    кому угодно без входа.
    """

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        from django.conf import settings as dj_settings

        email = (request.data.get("email") or "").strip().lower()
        payload = {
            "detail": (
                "Если аккаунт с таким адресом существует, мы отправили письмо со ссылкой "
                "для подтверждения удаления. Ссылка действует сутки."
            )
        }
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                link = send_confirmation_email(user)
                if dj_settings.DEBUG:
                    payload["confirm_link"] = link
        return Response(payload)


class PublicDeletionConfirmView(APIView):
    """POST /auth/account-deletion/confirm/ {token} — исполнить запрос из письма."""

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        token = request.data.get("token") or request.query_params.get("token")
        user_id = read_token(token or "")
        if not user_id:
            return Response(
                {"detail": "Ссылка недействительна или устарела.", "code": "invalid_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response(
                {"detail": "Ссылка недействительна или устарела.", "code": "invalid_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        purge_at = request_deletion(user)
        return Response(
            {
                "detail": (
                    f"Аккаунт заблокирован, данные будут удалены через {GRACE_DAYS} дней. "
                    f"Чтобы отменить удаление, войдите в приложение до этого срока."
                ),
                "grace_days": GRACE_DAYS,
                "purge_after": purge_at,
            }
        )
