"""Периодические задачи меню: очистка карантина и уход в архив по сроку."""

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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def archive_expired_menus(self):
    """MG_MENUEXPIRE: меню, чей календарный срок вышел, уходят в архив.

    Меню создаётся на период (`start_date`…`end_date`) и остаётся `active`
    навсегда: статус меняла только кнопка «в архив», которой ни в вебе, ни в
    приложении нет. За полгода в списке выбора накапливается десяток
    прошлогодних меню, и нужное приходится искать среди них.

    Архив — не удаление: меню остаётся в базе, открывается по ссылке и
    показывается в списке `?archived=true`. Из выбора уходит только то, чей
    последний день уже прошёл.

    День берётся местный (`localdate`, TIME_ZONE проекта), а не UTC: «срок
    вышел» — про календарь человека. В Москве иначе меню, кончившееся вчера,
    висело бы актуальным до трёх часов ночи.

    Задача — не единственная защита: список актуальных меню и так отсекает
    просроченные по дате (см. MenuListView). Она нужна, чтобы хранимый статус
    не расходился с тем, что человек видит, — по нему считают специалисты и
    отчёты.
    """
    try:
        from apps.menu.models import Menu

        today = timezone.localdate()
        cnt = Menu.objects.filter(status=Menu.Status.ACTIVE, end_date__lt=today).update(
            status=Menu.Status.ARCHIVED,
        )
        log.info("archive_expired_menus: в архив ушло %d меню (срок < %s)", cnt, today)
        return cnt
    except Exception as exc:
        log.error("archive_expired_menus error: %s", exc)
        raise self.retry(exc=exc)
