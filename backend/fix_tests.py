import pathlib, re

# --- fridge: len(resp.data) -> len(resp.data["results"]) ---
p = pathlib.Path("apps/fridge/tests/test_fridge.py")
t = p.read_text(encoding="utf-8")
t = t.replace(
    'assert len(resp.data) == 2',
    'assert len(resp.data["results"]) == 2'
)
t = t.replace(
    'assert len(resp.data) == 0',
    'assert len(resp.data["results"]) == 0'
)
p.write_text(t, encoding="utf-8")

# --- subscriptions: resp.data -> resp.data["results"] ---
p = pathlib.Path("apps/subscriptions/tests/test_subscriptions.py")
t = p.read_text(encoding="utf-8")
t = t.replace(
    'assert len(resp.data) >= 1',
    'assert resp.data["count"] >= 1'
)
t = t.replace(
    'for p in resp.data)',
    'for p in resp.data["results"])'
)
p.write_text(t, encoding="utf-8")

# --- webhook: use monkeypatch-friendly env via override_settings ---
p = pathlib.Path("apps/payments/tests/test_webhook.py")
t = p.read_text(encoding="utf-8")
# replace config() with settings override approach
t = t.replace(
    'secret = config("YOOKASSA_SECRET_KEY", default="")',
    'secret = getattr(settings, "YOOKASSA_SECRET_KEY", "")'
)
p.write_text(t, encoding="utf-8")

print("done")