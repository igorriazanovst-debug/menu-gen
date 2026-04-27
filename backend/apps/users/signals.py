"""
Сигналы users: автозаполнение целевых КБЖУ при сохранении Profile.
"""
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Profile
from .nutrition import fill_profile_targets


@receiver(pre_save, sender=Profile)
def auto_fill_targets(sender, instance: Profile, **kwargs):
    """
    Автозаполняет calorie_target/protein/fat/carbs/fiber_target_g
    если они пустые. Если пользователь задал значение вручную — не трогаем.
    """
    fill_profile_targets(instance, force=False)
