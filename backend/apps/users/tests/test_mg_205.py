"""
MG-205 tests: отслеживание источника правок целей КБЖУ.

Сценарии:
  1. auto: новый профиль → fill_profile_targets создаёт записи source='auto'
  2. user override: PATCH через UserMeUpdateSerializer → source='user', lock
  3. specialist override: PATCH через FamilyMemberUpdateSerializer от verified specialist'а с активным assignment → source='specialist'
  4. reset: force=True снимает lock и ставит source='auto'
  5. lock: при source='user' автоматический fill_profile_targets(force=False) НЕ перетирает
  6. AuditLog дублирование: при правке создаётся запись entity_type='profile_target'

Запуск:
  docker compose -f /opt/menugen/docker-compose.yml exec -T backend \
    pytest apps/users/tests/test_mg_205.py -v
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.users.models import Profile, ProfileTargetAudit
from apps.users.audit import (
    record_target_change,
    get_field_source,
    is_locked,
)
from apps.users.nutrition import fill_profile_targets
from apps.users.serializers import UserMeUpdateSerializer
from apps.family.serializers import FamilyMemberUpdateSerializer

User = get_user_model()
pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# Фикстуры
# --------------------------------------------------------------------------


@pytest.fixture
def user_with_profile():
    u = User.objects.create(name="Test User", email="mg205@test.local")
    u.set_password("xx")
    u.save()
    p = Profile.objects.create(
        user=u,
        birth_year=1990,
        gender=Profile.Gender.MALE,
        height_cm=180,
        weight_kg=Decimal("75"),
        activity_level=Profile.ActivityLevel.MODERATE,
        goal=Profile.Goal.MAINTAIN,
    )
    return u, p


@pytest.fixture
def specialist_user():
    """User с verified Specialist'ом, без assignment (assignment добавим в тесте)."""
    from apps.specialists.models import Specialist

    u = User.objects.create(name="Doc", email="doc@test.local")
    u.set_password("xx")
    u.save()
    sp = Specialist.objects.create(
        user=u,
        specialist_type=Specialist.Type.NUTRITIONIST if hasattr(Specialist.Type, "NUTRITIONIST") else list(Specialist.Type)[0],
        is_verified=True,
    )
    return u, sp


# --------------------------------------------------------------------------
# Тесты
# --------------------------------------------------------------------------


def test_01_auto_on_create(user_with_profile):
    """При создании профиля все 5 целей получают аудит-запись source='auto'."""
    _, p = user_with_profile

    audits = ProfileTargetAudit.objects.filter(profile=p)
    fields = set(audits.values_list("field", flat=True))
    expected = {
        "calorie_target",
        "protein_target_g",
        "fat_target_g",
        "carb_target_g",
        "fiber_target_g",
    }
    assert expected.issubset(fields), f"missing audit for: {expected - fields}"
    assert all(a.source == "auto" for a in audits), "all initial sources must be 'auto'"


def test_02_user_override_locks_field(user_with_profile):
    """PATCH через UserMeUpdateSerializer ставит source='user' и lock=True."""
    u, p = user_with_profile

    factory = APIRequestFactory()
    req = factory.patch("/api/v1/users/me", {})
    req.user = u

    ser = UserMeUpdateSerializer(
        instance=u,
        data={"profile": {"protein_target_g": "150.0"}},
        partial=True,
        context={"request": req},
    )
    ser.is_valid(raise_exception=True)
    ser.save()

    p.refresh_from_db()
    assert p.protein_target_g == Decimal("150.0")
    assert get_field_source(p, "protein_target_g") == "user"
    assert is_locked(p, "protein_target_g") is True

    # Другие поля остались source='auto'
    assert get_field_source(p, "fat_target_g") == "auto"


def test_03_lock_prevents_auto_overwrite(user_with_profile):
    """fill_profile_targets(force=False) НЕ перетирает залоченное поле."""
    u, p = user_with_profile

    # User override
    record_target_change(
        profile=p,
        field="protein_target_g",
        new_value=Decimal("200.0"),
        source="user",
        by_user=u,
        old_value=p.protein_target_g,
    )
    p.protein_target_g = Decimal("200.0")
    p.save()  # триггерит fill(force=False) — НЕ должен перетереть

    p.refresh_from_db()
    assert p.protein_target_g == Decimal("200.0"), \
        "залоченное поле перетёрто авторасчётом!"
    assert is_locked(p, "protein_target_g") is True


def test_04_force_resets_to_auto(user_with_profile):
    """force=True перетирает залоченное поле и ставит source='auto'."""
    u, p = user_with_profile

    record_target_change(
        profile=p, field="protein_target_g", new_value=Decimal("999.0"),
        source="user", by_user=u, old_value=p.protein_target_g,
    )
    p.protein_target_g = Decimal("999.0")
    p.save()
    assert is_locked(p, "protein_target_g")

    fill_profile_targets(p, force=True, actor=u)
    p.save()
    p.refresh_from_db()

    assert p.protein_target_g == Decimal(str(round(75 * 1.5, 1))), "force=True не пересчитал"
    assert get_field_source(p, "protein_target_g") == "auto"
    assert is_locked(p, "protein_target_g") is False


def test_05_specialist_override_via_family_serializer(user_with_profile, specialist_user):
    """Verified specialist с активным assignment правит профиль клиента → source='specialist'."""
    from apps.family.models import Family, FamilyMember
    from apps.specialists.models import SpecialistAssignment

    client_user, client_profile = user_with_profile
    doc_user, specialist = specialist_user

    family = Family.objects.create(owner=client_user, name="Test Family")
    member = FamilyMember.objects.create(
        family=family, user=client_user, role=FamilyMember.Role.HEAD
    )
    SpecialistAssignment.objects.create(
        family=family,
        specialist=specialist,
        specialist_type=specialist.specialist_type,
        status=SpecialistAssignment.Status.ACTIVE,
    )

    factory = APIRequestFactory()
    req = factory.patch(f"/api/v1/family/members/{member.id}", {})
    req.user = doc_user

    ser = FamilyMemberUpdateSerializer(
        instance=member,
        data={"profile": {"calorie_target": 1800}},
        partial=True,
        context={"request": req},
    )
    ser.is_valid(raise_exception=True)
    ser.save()

    client_profile.refresh_from_db()
    assert client_profile.calorie_target == 1800
    assert get_field_source(client_profile, "calorie_target") == "specialist"
    assert is_locked(client_profile, "calorie_target") is True


def test_06_user_self_via_family_is_user(user_with_profile):
    """Пользователь сам себе через family endpoint → source='user' (не 'specialist')."""
    from apps.family.models import Family, FamilyMember

    u, p = user_with_profile
    family = Family.objects.create(owner=u, name="My Family")
    member = FamilyMember.objects.create(family=family, user=u, role=FamilyMember.Role.HEAD)

    factory = APIRequestFactory()
    req = factory.patch(f"/api/v1/family/members/{member.id}", {})
    req.user = u

    ser = FamilyMemberUpdateSerializer(
        instance=member,
        data={"profile": {"fat_target_g": "70.0"}},
        partial=True,
        context={"request": req},
    )
    ser.is_valid(raise_exception=True)
    ser.save()

    p.refresh_from_db()
    assert p.fat_target_g == Decimal("70.0")
    assert get_field_source(p, "fat_target_g") == "user"


def test_07_audit_log_dublicate(user_with_profile):
    """Каждое изменение дублируется в общий AuditLog (entity_type='profile_target')."""
    from apps.sync.models import AuditLog

    u, p = user_with_profile

    before = AuditLog.objects.filter(
        entity_type="profile_target", entity_id=f"{p.id}:protein_target_g"
    ).count()

    record_target_change(
        profile=p, field="protein_target_g", new_value=Decimal("123.0"),
        source="user", by_user=u, old_value=p.protein_target_g, reason="test",
    )

    after = AuditLog.objects.filter(
        entity_type="profile_target", entity_id=f"{p.id}:protein_target_g"
    ).count()
    assert after == before + 1

    last = AuditLog.objects.filter(
        entity_type="profile_target", entity_id=f"{p.id}:protein_target_g"
    ).order_by("-id").first()
    assert last.action == "profile_target.update"
    assert last.new_values["source"] == "user"
    assert last.new_values["by_user_id"] == u.id


def test_08_history_chronological(user_with_profile):
    """История правок одного поля выстраивается во времени корректно."""
    u, p = user_with_profile

    # 1) initial auto уже есть от save()
    # 2) user override
    record_target_change(p, "calorie_target", 2500, "user", u, old_value=p.calorie_target)
    # 3) specialist override
    record_target_change(p, "calorie_target", 2200, "specialist", u, old_value=2500)
    # 4) reset to auto
    record_target_change(p, "calorie_target", 2077, "auto", None, old_value=2200)

    history = list(
        ProfileTargetAudit.objects.filter(profile=p, field="calorie_target")
        .order_by("at")
        .values_list("source", flat=True)
    )
    # Ожидаем: auto (initial), user, specialist, auto
    assert history[-3:] == ["user", "specialist", "auto"]
    assert get_field_source(p, "calorie_target") == "auto"
