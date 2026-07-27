import os

from rest_framework import serializers

from .models import LegalInfo


class LegalInfoSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = LegalInfo
        fields = (
            "company_name",
            "inn",
            "ogrnip",
            "legal_address",
            "email",
            "phone",
            "bank_name",
            "bank_bik",
            "bank_account",
            "corr_account",
            "requisites_extra",
            "offer_text",
            "logo_url",
            "updated_at",
        )

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        url = obj.logo.url  # /media/legal/...
        public = (os.environ.get("BACKEND_PUBLIC_URL") or "").rstrip("/")
        if public and url.startswith("/"):
            return public + url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url
