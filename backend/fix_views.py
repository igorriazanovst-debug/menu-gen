import pathlib

p = pathlib.Path("apps/payments/views.py")
t = p.read_text(encoding="utf-8")
t = t.replace(
    'secret = config("YOOKASSA_SECRET_KEY", default="")',
    'from django.conf import settings as django_settings\n        secret = getattr(django_settings, "YOOKASSA_SECRET_KEY", config("YOOKASSA_SECRET_KEY", default=""))'
)
p.write_text(t, encoding="utf-8")
print("done")