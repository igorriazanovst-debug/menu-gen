"""MG_LINKASYNC: пересборка связей рецепт→продукт — фоном, а не в запросе.

Связи строит ИИ: каждый сегмент состава уходит в модель на канонизацию
(`recipe_products.canonicalize_and_categorize`). Это десятки секунд — при
`AI_TIMEOUT=30` и разбиении по 30 сегментов один рецепт легко упирается в два
чанка плюс повторный проход. Пока это висело в post_save, сохранение рецепта в
админке регулярно отдавало `504 Gateway Time-out`: nginx не дожидался ответа.
"""

import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def rebuild_recipe_links_task(self, recipe_id: int):
    """Пересобирает RecipeProduct для одного рецепта. Возвращает число связей."""
    from .models import Recipe
    from .recipe_products import rebuild_recipe_links

    recipe = Recipe.objects.filter(pk=recipe_id).first()
    if recipe is None:
        # Рецепт удалили, пока задача ждала очереди — это не ошибка.
        log.info("rebuild_recipe_links_task: рецепт %s не найден", recipe_id)
        return 0

    try:
        count = rebuild_recipe_links(recipe, force=True, create_missing=True)
        log.info("rebuild_recipe_links_task: рецепт %s, связей %d", recipe_id, count)
        return count
    except Exception as exc:  # noqa: BLE001 — причина уходит в лог и в retry
        log.error("rebuild_recipe_links_task: рецепт %s — %s", recipe_id, exc)
        raise self.retry(exc=exc)
