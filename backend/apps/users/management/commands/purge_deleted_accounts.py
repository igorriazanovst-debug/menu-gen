"""MG_ACCDEL: стирание аккаунтов, чья отсрочка истекла.

Запускается по расписанию. Без --apply НИЧЕГО не удаляет и только печатает
список — команда разрушительная и необратимая, а список показывается целиком.

    docker compose run -d --name mg-purge backend python manage.py purge_deleted_accounts
    docker logs mg-purge
    docker compose run -d --name mg-purge-apply backend python manage.py purge_deleted_accounts --apply
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.users.account_deletion import GRACE_DAYS, due_for_purge, purge_after, purge_user


class Command(BaseCommand):
    help = f"Стирает аккаунты, запросившие удаление более {GRACE_DAYS} дней назад."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Действительно удалить. Без этого флага — только показать список.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        users = list(due_for_purge(now).order_by("deletion_requested_at"))

        self.stdout.write(f"Отсрочка: {GRACE_DAYS} дней. Сейчас: {now:%Y-%m-%d %H:%M} UTC.")
        if not users:
            self.stdout.write("Стирать нечего.")
            return

        self.stdout.write(f"К стиранию: {len(users)}")
        for user in users:
            self.stdout.write(
                f"  id={user.id}  {user.email or user.phone or f'vk:{user.vk_id}'}  "
                f"запрошено {user.deletion_requested_at:%Y-%m-%d}, "
                f"срок истёк {purge_after(user.deletion_requested_at):%Y-%m-%d}"
            )

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Пробный прогон. Чтобы удалить, повторите с --apply."))
            return

        totals = {"families_transferred": 0, "families_deleted": 0, "managed_deleted": 0}
        for user in users:
            report = purge_user(user)
            for key in totals:
                totals[key] += report[key]
        self.stdout.write(
            self.style.SUCCESS(
                f"Стёрто аккаунтов: {len(users)}. "
                f"Семей передано: {totals['families_transferred']}, "
                f"удалено: {totals['families_deleted']}, "
                f"управляемых участников удалено: {totals['managed_deleted']}."
            )
        )
