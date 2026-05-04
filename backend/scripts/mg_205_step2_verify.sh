#!/usr/bin/env bash
# MG-205 step 2 verify: убедиться что force=True+save() корректно перетирает.
# Read-only-ish: возвращает pid=1 в исходное состояние (auto, 112.5).
set -u
COMPOSE="docker compose -f /opt/menugen/docker-compose.yml"

${COMPOSE} exec -T backend python manage.py shell <<'PYEOF'
from apps.users.models import Profile, ProfileTargetAudit
from apps.users.audit import get_field_source, is_locked
from apps.users.nutrition import fill_profile_targets

p = Profile.objects.get(id=1)
print("[before] cal=%s P=%s F=%s C=%s Fb=%s" % (
    p.calorie_target, p.protein_target_g, p.fat_target_g, p.carb_target_g, p.fiber_target_g))
print("[before] sources:")
for f in ("calorie_target","protein_target_g","fat_target_g","carb_target_g","fiber_target_g"):
    print(f"   {f}: {get_field_source(p, f)} locked={is_locked(p, f)}")

# protein сейчас = 130, source=auto (потому что в прошлом шаге force=True записал auto-аудит, но БД не обновилась)
# Зовём force=True ещё раз и СОХРАНЯЕМ
fill_profile_targets(p, force=True, actor=p.user)
print("[after fill force=True, before save] protein on instance:", p.protein_target_g)
p.save()  # save() запустит ещё один fill_profile_targets(force=False) и super().save()
p.refresh_from_db()
print("[after save] cal=%s P=%s F=%s C=%s Fb=%s" % (
    p.calorie_target, p.protein_target_g, p.fat_target_g, p.carb_target_g, p.fiber_target_g))

# Полный audit trail
print("[audit history protein_target_g]")
for pta in ProfileTargetAudit.objects.filter(profile=p, field="protein_target_g").order_by("at"):
    print(f"   {pta.at:%H:%M:%S} src={pta.source} old={pta.old_value} new={pta.new_value} reason='{pta.reason[:50]}'")

# Проверка: для save() БЕЗ force= после lock pollution — поле не должно меняться,
# но мы только что force=True+save сделали, значит source=auto, lock=False — лок ушёл.
print("[final check] protein lock state:", is_locked(p, "protein_target_g"))
PYEOF
