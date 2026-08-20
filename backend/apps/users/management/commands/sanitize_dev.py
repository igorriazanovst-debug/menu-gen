"""MG_DEVMIRROR: обезличить копию прода на dev-контуре.

Запускается сразу после восстановления боевого дампа на dev. Задача — снять с
копии то, чем можно достать живого человека или боевую систему, и при этом
оставить данные пригодными для воспроизведения багов: меню, рецепты, списки,
холодильник, подписки остаются как есть.

Что делается (всё идемпотентно, повторный запуск безопасен):

* e-mail и имена обычных пользователей заменяются на `user<id>@dev.local`;
  пароль становится неиспользуемым — войти под чужой учёткой нельзя, и украденный
  dev-дамп не даёт материала для подбора боевых паролей;
* сотрудники (`is_staff`) не трогаются: под ними заходят в админку dev;
* телефоны и подтверждения телефона стираются вместе с привязками к чатам
  мессенджеров — иначе бот с dev напишет живому человеку;
* токены соцсетей стираются;
* у платежей обнуляется идентификатор у провайдера: ни одно действие на dev не
  должно уметь дотянуться до настоящего платежа в ЮKassa;
* периодические задачи выключаются: рассылка «что портится в холодильнике» с
  копии прода ушла бы настоящим адресатам.

Защита от запуска на проде: команда работает только при `MENUGEN_ENV=dev`.
Значение по умолчанию — `prod`, поэтому сервер без явной пометки командой не
обрабатывается. Плюс подтверждение `--yes`.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Обезличить копию боевых данных на dev-контуре (MENUGEN_ENV=dev)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Подтверждение: данные будут изменены необратимо.",
        )
        parser.add_argument(
            "--keep-emails",
            default="",
            help="Через запятую — адреса, которые оставить как есть (кроме сотрудников).",
        )

    def handle(self, *args, **options):
        env = getattr(settings, "MENUGEN_ENV", "prod")
        if env != "dev":
            raise CommandError(
                f"MENUGEN_ENV={env!r}: команда работает только на dev-контуре. "
                "Если это действительно dev — добавьте MENUGEN_ENV=dev в .env и перезапустите backend."
            )
        if not options["yes"]:
            raise CommandError("Нужен --yes: команда необратимо меняет данные.")

        keep = {e.strip().lower() for e in options["keep_emails"].split(",") if e.strip()}

        with transaction.atomic():
            users = self._users(keep)
            phones = self._phones()
            social = self._social()
            payments = self._payments()
            beat = self._beat()

        self.stdout.write(self.style.SUCCESS("Обезличено:"))
        self.stdout.write(f"  пользователей: {users}")
        self.stdout.write(f"  подтверждений телефона удалено: {phones}")
        self.stdout.write(f"  привязок соцсетей очищено: {social}")
        self.stdout.write(f"  платежей отвязано от провайдера: {payments}")
        self.stdout.write(f"  периодических задач выключено: {beat}")

    def _users(self, keep):
        from apps.users.models import User

        qs = User.objects.filter(is_staff=False, is_superuser=False)
        if keep:
            qs = qs.exclude(email__in=keep)
        n = 0
        for user in qs.iterator(chunk_size=500):
            user.email = f"user{user.id}@dev.local"
            user.name = f"Пользователь {user.id}"
            user.phone = None
            user.avatar_url = None
            # set_unusable_password, а не удаление хеша: боевой хеш не должен
            # уезжать на dev даже в нечитаемом виде.
            user.set_unusable_password()
            user.save(update_fields=["email", "name", "phone", "avatar_url", "password"])
            n += 1
        return n

    def _phones(self):
        from apps.users.models import PhoneVerification

        n, _ = PhoneVerification.objects.all().delete()
        return n

    def _social(self):
        from apps.social.models import SocialLink

        return SocialLink.objects.update(access_token="", is_active=False)

    def _payments(self):
        from apps.payments.models import Payment

        n = 0
        # payment_id уникален, поэтому обнуляем поштучно значением NULL.
        for pid in Payment.objects.filter(payment_id__isnull=False).values_list("id", flat=True):
            Payment.objects.filter(id=pid).update(payment_id=None)
            n += 1
        return n

    def _beat(self):
        try:
            from django_celery_beat.models import PeriodicTask
        except ImportError:  # пакета нет — расписаний тоже
            return 0
        return PeriodicTask.objects.filter(enabled=True).exclude(name__startswith="celery.").update(enabled=False)
