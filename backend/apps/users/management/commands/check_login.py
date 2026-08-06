"""MG_LOGINFIX: почему аккаунт не может войти — и как его разблокировать.

Вход отдаёт наружу одинаково скупые ответы (и правильно делает: по ним нельзя
перебирать чужие адреса). Из-за этого «не работает вход» со стороны сервера не
диагностируется вообще никак. Команда показывает всё, что на самом деле влияет
на вход конкретного аккаунта:

    python manage.py check_login user@example.ru

Отдельно — список тех, кого держит гейт подтверждения e-mail:

    python manage.py check_login --all-unverified

И разблокировка вручную (аккаунт заведён администратором, письма не ходят):

    python manage.py check_login user@example.ru --verify
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

User = get_user_model()


def gate_enabled() -> bool:
    return bool(getattr(settings, "EMAIL_VERIFICATION_REQUIRED", True))


def login_blockers(user) -> list[str]:
    """Причины, по которым /auth/login/ откажет этому пользователю."""
    reasons = []
    if not user.is_active:
        reasons.append("аккаунт отключён (is_active=False)")
    if not user.has_usable_password():
        reasons.append("пароль не задан (unusable password) — вход по паролю невозможен")
    if gate_enabled() and user.email and not user.is_email_verified:
        reasons.append("e-mail не подтверждён, а гейт включён (EMAIL_VERIFICATION_REQUIRED=True)")
    return reasons


class Command(BaseCommand):
    help = "Диагностика входа: почему аккаунт получает отказ на /auth/login/."

    def add_arguments(self, parser):
        parser.add_argument("identifier", nargs="*", help="e-mail или телефон")
        parser.add_argument(
            "--all-unverified",
            action="store_true",
            help="показать всех, кого блокирует гейт подтверждения e-mail",
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            help="пометить e-mail подтверждённым (разблокировать вход)",
        )

    def handle(self, *args, **opts):
        self.stdout.write(f"EMAIL_VERIFICATION_REQUIRED = {gate_enabled()}")

        if opts["all_unverified"]:
            self._report_unverified(opts["verify"])
            return

        identifiers = opts["identifier"]
        if not identifiers:
            raise CommandError("Укажите e-mail/телефон или --all-unverified")

        for identifier in identifiers:
            self._report_one(identifier, opts["verify"])

    def _find(self, identifier: str):
        value = identifier.strip()
        return User.objects.filter(email__iexact=value).first() or User.objects.filter(phone=value).first()

    def _report_one(self, identifier: str, verify: bool):
        user = self._find(identifier)
        self.stdout.write("")
        if not user:
            self.stdout.write(self.style.ERROR(f"{identifier}: пользователя нет в этой базе"))
            return

        self.stdout.write(f"{identifier} → id={user.id}")
        self.stdout.write(f"  e-mail:      {user.email or '—'}")
        self.stdout.write(f"  телефон:     {user.phone or '—'}")
        self.stdout.write(f"  активен:     {user.is_active}")
        self.stdout.write(f"  пароль:      {'задан' if user.has_usable_password() else 'НЕ задан'}")
        self.stdout.write(f"  e-mail подтверждён: {user.email_verified_at or 'нет'}")
        self.stdout.write(f"  роль:        {user.user_type} (staff={user.is_staff}, super={user.is_superuser})")

        blockers = login_blockers(user)
        if blockers:
            for reason in blockers:
                self.stdout.write(self.style.ERROR(f"  ✗ {reason}"))
        else:
            self.stdout.write(self.style.SUCCESS("  ✓ вход разрешён — остаётся только пароль"))

        if verify and user.email and not user.is_email_verified:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
            self.stdout.write(self.style.SUCCESS("  → e-mail помечен подтверждённым"))

    def _report_unverified(self, verify: bool):
        blocked = User.objects.filter(email_verified_at__isnull=True).exclude(email__isnull=True).exclude(email="")
        count = blocked.count()
        self.stdout.write(f"Аккаунтов с неподтверждённым e-mail: {count}")
        for user in blocked.order_by("id")[:200]:
            self.stdout.write(f"  id={user.id} {user.email} (создан {user.created_at:%Y-%m-%d})")
        if verify and count:
            blocked.update(email_verified_at=timezone.now())
            self.stdout.write(self.style.SUCCESS(f"Помечено подтверждёнными: {count}"))
