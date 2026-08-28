"""MG_ACCDEL: периодическое стирание аккаунтов с истёкшей отсрочкой.

Отдельного cron не заводим: в проекте уже работает celery-beat, и расписание
живёт рядом с остальными (config/settings.py, CELERY_BEAT_SCHEDULE).

Задача, в отличие от одноимённой management-команды, удаляет сразу и без
--apply. Так и задумано: пробный прогон защищает человека за консолью, который
может ошибиться в выборке, а здесь выборка одна и та же каждый раз, и защита
другая — тридцать дней, которые аккаунт лежал замороженным и мог быть возвращён
одним входом.
"""

import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def purge_deleted_accounts(self):
    """Стирает аккаунты, чья отсрочка истекла. Возвращает счётчики для лога."""
    try:
        from apps.users.account_deletion import due_for_purge, purge_user

        totals = {"purged": 0, "families_transferred": 0, "families_deleted": 0, "managed_deleted": 0}
        # Список материализуем заранее: purge_user удаляет строки, и ленивый
        # queryset пришлось бы перечислять по изменяющейся выборке.
        for user in list(due_for_purge().order_by("deletion_requested_at")):
            report = purge_user(user)
            totals["purged"] += 1
            for key in ("families_transferred", "families_deleted", "managed_deleted"):
                totals[key] += report[key]

        if totals["purged"]:
            log.info("MG_ACCDEL: плановое стирание — %s", totals)
        return totals
    except Exception as e:
        log.error("MG_ACCDEL: плановое стирание не удалось: %s", e)
        raise self.retry(exc=e)
