"""MG-608: периодическая очистка карантина меню (purge_after < now)."""

import logging

from celery import shared_task
from django.utils import timezone

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def purge_expired_menus(self):
    """Удаляет DeletedMenu, у которых purge_after уже прошёл."""
    try:
        from apps.menu.models import DeletedMenu

        now = timezone.now()
        qs = DeletedMenu.objects.filter(purge_after__lt=now)
        cnt = qs.count()
        if cnt:
            qs.delete()
        log.info("purge_expired_menus: удалено %d записей", cnt)
        return cnt
    except Exception as exc:
        log.error("purge_expired_menus error: %s", exc)
        raise self.retry(exc=exc)
