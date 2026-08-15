# MG_RECIPELINK — rebuild product links when a recipe is saved.
#
# MG_LINKASYNC: пересборка ходит в ИИ и занимает десятки секунд. В запросе ей
# не место — сохранение рецепта в админке регулярно отдавало 504. Теперь задача
# уходит в Celery, и только когда состав действительно изменился: правка
# названия, флагов или фото связей не касается.
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Recipe

log = logging.getLogger(__name__)


def ingredients_changed(instance, created: bool) -> bool:
    """Нужно ли пересобирать связи после сохранения.

    Новый рецепт — всегда. У загруженного из базы сравниваем состав со снимком,
    сделанным при загрузке (`Recipe.from_db`). Снимка нет — объект собрали в
    коде, а не прочитали; тогда считаем, что изменился: пропустить пересборку
    хуже, чем сделать лишнюю.
    """
    if created:
        return True
    snapshot = getattr(instance, "_mg_ingredients_snapshot", None)
    if snapshot is None:
        return True
    return snapshot != Recipe.ingredients_fingerprint(instance.ingredients)


@receiver(post_save, sender=Recipe)
def _mg_recipelink_on_recipe_save(sender, instance, created=False, **kwargs):
    if getattr(instance, "_mg_skip_link_rebuild", False):
        return

    changed = ingredients_changed(instance, created)
    # Состав записан — дальше он и есть точка отсчёта. Иначе повторное
    # сохранение того же объекта (админка сохраняет форму и инлайны отдельно)
    # ставило бы задачу второй раз.
    instance._mg_ingredients_snapshot = Recipe.ingredients_fingerprint(instance.ingredients)

    if not changed:
        return
    if not instance.ingredients:
        return  # нечего канонизировать — и ИИ дёргать незачем

    recipe_id = instance.pk

    def _enqueue():
        from .tasks import rebuild_recipe_links_task

        try:
            rebuild_recipe_links_task.delay(recipe_id)
        except Exception as exc:  # брокер недоступен — сохранение не роняем
            log.error(
                "Не удалось поставить пересборку связей для рецепта %s: %s. "
                "Починить: manage.py mg_backfill_recipe_products --force --recipe %s",
                recipe_id,
                exc,
                recipe_id,
            )

    # После коммита: воркер не должен увидеть рецепт раньше, чем тот записан.
    transaction.on_commit(_enqueue)
