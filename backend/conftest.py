from django.conf import settings


def pytest_configure(config):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.REST_FRAMEWORK = {
        **getattr(settings, "REST_FRAMEWORK", {}),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    }
