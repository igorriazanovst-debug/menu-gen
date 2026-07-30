"""MG_LEGAL: юридическая информация сайта (реквизиты ИП, оферта, логотип).

Синглтон: одна запись, редактируется в админке. Публично отдаётся через API,
на вебе — страницы «Реквизиты» и «Оферта».
"""

from django.db import models


class LegalInfo(models.Model):
    # Реквизиты ИП
    company_name = models.CharField(
        max_length=255, blank=True, verbose_name="Наименование", help_text="Напр. «ИП Иванов Иван Иванович»"
    )
    inn = models.CharField(max_length=20, blank=True, verbose_name="ИНН")
    ogrnip = models.CharField(max_length=20, blank=True, verbose_name="ОГРНИП")
    legal_address = models.CharField(max_length=500, blank=True, verbose_name="Адрес")
    email = models.CharField(max_length=255, blank=True, verbose_name="E-mail")
    phone = models.CharField(max_length=64, blank=True, verbose_name="Телефон")

    # Банковские реквизиты (опционально)
    bank_name = models.CharField(max_length=255, blank=True, verbose_name="Банк")
    bank_bik = models.CharField(max_length=20, blank=True, verbose_name="БИК")
    bank_account = models.CharField(max_length=34, blank=True, verbose_name="Расчётный счёт")
    corr_account = models.CharField(max_length=34, blank=True, verbose_name="Корр. счёт")

    requisites_extra = models.TextField(blank=True, verbose_name="Доп. реквизиты (свободный текст)")

    # Оферта
    offer_text = models.TextField(blank=True, verbose_name="Текст оферты")

    # MG_PRIVACY: Политика обработки персональных данных (152-ФЗ). Если поле
    # пустое — отдаётся типовой текст с подстановкой реквизитов (см.
    # privacy_default.py), чтобы страница не была пустой.
    privacy_text = models.TextField(
        blank=True,
        verbose_name="Текст политики обработки ПД",
        help_text="Если оставить пустым — на сайте показывается типовой текст с вашими реквизитами.",
    )

    # Логотип (пока заглушка-помидор на вебе, если не задан)
    logo = models.ImageField(upload_to="legal/", null=True, blank=True, verbose_name="Логотип")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "legal_info"
        verbose_name = "Юридическая информация"
        verbose_name_plural = "Юридическая информация"

    def __str__(self):
        return self.company_name or "Юридическая информация"

    # ── Синглтон ─────────────────────────────────────────────────────────────
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Синглтон не удаляем.
        pass

    @classmethod
    def load(cls) -> "LegalInfo":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # MG_PRIVACY ─────────────────────────────────────────────────────────────
    @property
    def privacy_effective(self) -> str:
        """Текст политики: свой из админки, иначе типовой с реквизитами."""
        own = (self.privacy_text or "").strip()
        if own:
            return own
        from .privacy_default import default_privacy_text

        return default_privacy_text(self)
