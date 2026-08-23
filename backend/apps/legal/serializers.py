import os

from rest_framework import serializers

from .models import AndroidBuild, LegalInfo


class LegalInfoSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    # MG_PRIVACY: отдаём действующий текст политики (свой либо типовой).
    privacy_text = serializers.CharField(source="privacy_effective", read_only=True)

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
            "privacy_text",  # MG_PRIVACY
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


class AndroidBuildSerializer(serializers.ModelSerializer):
    """MG_APKSITE: то, что показывает страница входа."""

    url = serializers.SerializerMethodField()

    class Meta:
        model = AndroidBuild
        fields = ("version_name", "version_code", "url", "size_bytes", "sha256", "notes", "created_at")

    def get_url(self, obj):
        if not obj.file:
            return None
        url = obj.file.url  # /media/apk/...
        public = (os.environ.get("BACKEND_PUBLIC_URL") or "").rstrip("/")
        if public and url.startswith("/"):
            return public + url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url
