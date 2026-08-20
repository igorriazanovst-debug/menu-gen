"""MG_TRAINER: инструменты тренера — сводка недели, вес, история целей, задания.

Тренеру доступны профиль (правка), дневник и меню (чтение). Из этого набора
он собирает свою петлю: поставил коридор → клиент ест → вес двигается или нет.
Раньше видимой была только первая часть: дневник листался по одному дню, вес
хранился одним перезаписываемым числом, история правок целей писалась в базу,
но нигде не показывалась, а рекомендации клиенту были не видны вовсе.

Проверяется и обратное: повару всё это закрыто — у него в матрице нет дневника.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.diary.models import DiaryEntry, WaterLog, WeightLog
from apps.family.models import Family, FamilyMember
from apps.specialists.models import Recommendation, Specialist, SpecialistAssignment
from apps.users.models import Profile, ProfileTargetAudit, User


@pytest.fixture
def client_family(db):
    user = User.objects.create_user(email="client@example.com", name="Клиент", password="pass12345")
    family = Family.objects.create(owner=user, name="Семья клиента")
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    Profile.objects.update_or_create(
        user=user,
        defaults={"height_cm": 180, "weight_kg": Decimal("80.0"), "calorie_target": 2400},
    )
    return family, user, member


def make_specialist(email, spec_type):
    user = User.objects.create_user(email=email, name=email.split("@")[0], password="pass12345")
    prof = Specialist.objects.create(user=user, specialist_type=spec_type, is_verified=True)
    return user, prof


def assign(prof, family, spec_type=None, status=SpecialistAssignment.Status.ACTIVE):
    return SpecialistAssignment.objects.create(
        family=family,
        specialist=prof,
        specialist_type=spec_type or prof.specialist_type,
        status=status,
    )


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def eat(member, day, calories, proteins=0, planned=False):
    return DiaryEntry.objects.create(
        member=member,
        date=day,
        meal_type=DiaryEntry.MealType.LUNCH,
        custom_name="Еда",
        nutrition={"calories": calories, "proteins": proteins, "fats": 0, "carbs": 0},
        is_eaten=True,
        is_planned=planned,
    )


@pytest.mark.django_db
class TestWeekSummary:
    def test_соблюдение_и_средние_считаются_по_дневнику(self, client_family):
        family, _, member = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        today = timezone.localdate()
        eat(member, today, 2000, proteins=120, planned=True)
        eat(member, today - timedelta(days=1), 2400, proteins=100)
        WaterLog.objects.create(member=member, date=today, water_ml=1500)

        r = api(trainer_user).get(reverse("cabinet-client-summary", args=[family.id]))

        assert r.status_code == 200, r.data
        me = r.data["members"][0]
        assert me["days_tracked"] == 2
        assert me["days_on_plan"] == 1
        # Среднее — по дням с записями, а не по всей неделе.
        assert me["avg_per_tracked_day"]["calories"] == 2200
        assert me["avg_per_tracked_day"]["proteins"] == 110.0
        assert me["targets"]["calories"] == 2400
        assert me["water"]["total_ml"] == 1500

    def test_среднее_не_делится_на_дни_без_записей(self, client_family):
        """Делить на 7 при трёх записях — показать втрое заниженный калораж."""
        family, _, member = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        eat(member, timezone.localdate(), 1800)

        r = api(trainer_user).get(reverse("cabinet-client-summary", args=[family.id]))

        assert r.data["members"][0]["avg_per_tracked_day"]["calories"] == 1800

    def test_незапланированное_не_считается_соблюдением(self, client_family):
        family, _, member = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        eat(member, timezone.localdate(), 3000, planned=False)

        r = api(trainer_user).get(reverse("cabinet-client-summary", args=[family.id]))

        me = r.data["members"][0]
        assert me["days_tracked"] == 1
        assert me["days_on_plan"] == 0

    def test_старое_за_пределами_периода_не_попадает(self, client_family):
        family, _, member = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        eat(member, timezone.localdate() - timedelta(days=30), 5000)

        r = api(trainer_user).get(reverse("cabinet-client-summary", args=[family.id]))

        assert r.data["members"][0]["days_tracked"] == 0

    def test_повару_сводка_закрыта(self, client_family):
        """У повара в матрице нет дневника — свёрнутый дневник тоже дневник."""
        family, _, _ = client_family
        cook_user, prof = make_specialist("cook@example.com", Specialist.Type.COOK)
        assign(prof, family)

        r = api(cook_user).get(reverse("cabinet-client-summary", args=[family.id]))

        assert r.status_code == 403

    def test_без_активного_назначения_чужая_семья_не_видна(self, client_family):
        family, _, _ = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family, status=SpecialistAssignment.Status.ENDED)

        r = api(trainer_user).get(reverse("cabinet-client-summary", args=[family.id]))

        assert r.status_code == 403


@pytest.mark.django_db
class TestWeight:
    def test_клиент_записывает_вес(self, client_family):
        _, user, member = client_family

        r = api(user).post(
            reverse("diary-weight"), {"date": str(timezone.localdate()), "weight_kg": "79.4"}, format="json"
        )

        assert r.status_code == 200, r.data
        assert WeightLog.objects.get(member=member).weight_kg == Decimal("79.4")

    def test_повторная_запись_за_день_правит_её_же(self, client_family):
        """Перевзвесился — это уточнение замера, а не вторая точка на графике."""
        _, user, member = client_family
        day = str(timezone.localdate())

        api(user).post(reverse("diary-weight"), {"date": day, "weight_kg": "79.4"}, format="json")
        api(user).post(reverse("diary-weight"), {"date": day, "weight_kg": "79.1"}, format="json")

        assert WeightLog.objects.filter(member=member).count() == 1
        assert WeightLog.objects.get(member=member).weight_kg == Decimal("79.1")

    def test_последний_замер_попадает_в_профиль(self, client_family):
        _, user, _ = client_family

        api(user).post(
            reverse("diary-weight"), {"date": str(timezone.localdate()), "weight_kg": "78.0"}, format="json"
        )

        user.profile.refresh_from_db()
        assert user.profile.weight_kg == Decimal("78.0")

    def test_правка_старого_замера_не_откатывает_профиль(self, client_family):
        _, user, _ = client_family
        today = timezone.localdate()
        api(user).post(reverse("diary-weight"), {"date": str(today), "weight_kg": "78.0"}, format="json")

        api(user).post(
            reverse("diary-weight"),
            {"date": str(today - timedelta(days=10)), "weight_kg": "85.0"},
            format="json",
        )

        user.profile.refresh_from_db()
        assert user.profile.weight_kg == Decimal("78.0")

    def test_нелепый_вес_отклоняется(self, client_family):
        _, user, _ = client_family

        r = api(user).post(
            reverse("diary-weight"), {"date": str(timezone.localdate()), "weight_kg": "0"}, format="json"
        )

        assert r.status_code == 400

    def test_тренер_видит_точки_веса(self, client_family):
        family, user, member = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        today = timezone.localdate()
        WeightLog.objects.create(member=member, date=today - timedelta(days=7), weight_kg=Decimal("81.0"))
        WeightLog.objects.create(member=member, date=today, weight_kg=Decimal("79.5"))

        r = api(trainer_user).get(reverse("cabinet-client-weight", args=[family.id]))

        assert r.status_code == 200, r.data
        points = r.data["members"][0]["points"]
        assert [p["weight_kg"] for p in points] == [81.0, 79.5]

    def test_динамика_веса_в_сводке(self, client_family):
        family, _, member = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        today = timezone.localdate()
        WeightLog.objects.create(member=member, date=today - timedelta(days=6), weight_kg=Decimal("81.0"))
        WeightLog.objects.create(member=member, date=today, weight_kg=Decimal("79.5"))

        r = api(trainer_user).get(reverse("cabinet-client-summary", args=[family.id]))

        weight = r.data["members"][0]["weight"]
        assert weight["change_kg"] == -1.5
        assert weight["points"] == 2

    def test_повару_вес_закрыт(self, client_family):
        family, _, _ = client_family
        cook_user, prof = make_specialist("cook@example.com", Specialist.Type.COOK)
        assign(prof, family)

        r = api(cook_user).get(reverse("cabinet-client-weight", args=[family.id]))

        assert r.status_code == 403


@pytest.mark.django_db
class TestTargetsHistory:
    def test_видно_кто_менял_цель(self, client_family):
        family, user, _ = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        ProfileTargetAudit.objects.create(
            profile=user.profile,
            field=ProfileTargetAudit.Field.CALORIE,
            source=ProfileTargetAudit.Source.SPECIALIST,
            by_user=trainer_user,
            old_value=Decimal("2400"),
            new_value=Decimal("2900"),
            reason="набор массы",
        )

        r = api(trainer_user).get(reverse("cabinet-client-targets-history", args=[family.id]))

        assert r.status_code == 200, r.data
        changes = r.data["members"][0]["changes"]
        assert changes[0]["field"] == "calorie_target"
        assert changes[0]["source"] == "specialist"
        assert changes[0]["by"] == trainer_user.name
        assert changes[0]["new_value"] == 2900.0

    def test_повару_история_целей_закрыта_на_запись_но_видна_на_чтение(self, client_family):
        """У повара профиль на чтение — историю целей он видит, править не может."""
        family, _, _ = client_family
        cook_user, prof = make_specialist("cook@example.com", Specialist.Type.COOK)
        assign(prof, family)

        r = api(cook_user).get(reverse("cabinet-client-targets-history", args=[family.id]))

        assert r.status_code == 200


@pytest.mark.django_db
class TestClientRecommendations:
    def _make_rec(self, family, prof, member, name="Планка 3×60 сек"):
        assignment = SpecialistAssignment.objects.filter(family=family, specialist=prof).first()
        return Recommendation.objects.create(
            assignment=assignment,
            family=family,
            member=member,
            rec_type=Recommendation.Type.EXERCISE,
            name=name,
            frequency="ежедневно",
        )

    def test_клиент_видит_рекомендации(self, client_family):
        family, user, member = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        self._make_rec(family, prof, member)

        r = api(user).get(reverse("my-recommendations"))

        assert r.status_code == 200, r.data
        assert r.data[0]["name"] == "Планка 3×60 сек"
        assert r.data[0]["specialist_name"] == trainer_user.name
        assert r.data[0]["specialist_type"] == "trainer"

    def test_первый_просмотр_показывает_запись_непрочитанной(self, client_family):
        """Иначе новое от старого не отличить: всё приходит уже прочитанным."""
        family, user, member = client_family
        _, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        rec = self._make_rec(family, prof, member)

        first = api(user).get(reverse("my-recommendations"))
        second = api(user).get(reverse("my-recommendations"))

        assert first.data[0]["is_read"] is False
        assert second.data[0]["is_read"] is True
        rec.refresh_from_db()
        assert rec.is_read is True

    def test_чужие_рекомендации_не_видны(self, client_family):
        family, _, member = client_family
        _, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        self._make_rec(family, prof, member)
        stranger = User.objects.create_user(email="other@example.com", name="Чужой", password="pass12345")
        other_family = Family.objects.create(owner=stranger, name="Чужая семья")
        FamilyMember.objects.create(family=other_family, user=stranger, role=FamilyMember.Role.HEAD)

        r = api(stranger).get(reverse("my-recommendations"))

        assert r.data == []

    def test_клиент_отмечает_выполнение(self, client_family):
        family, user, member = client_family
        _, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        rec = self._make_rec(family, prof, member)

        r = api(user).post(reverse("my-recommendation-done", args=[rec.id]), {}, format="json")

        assert r.status_code == 200, r.data
        rec.refresh_from_db()
        assert rec.completed_at is not None

    def test_отметку_можно_снять(self, client_family):
        family, user, member = client_family
        _, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        rec = self._make_rec(family, prof, member)
        api(user).post(reverse("my-recommendation-done", args=[rec.id]), {}, format="json")

        api(user).post(reverse("my-recommendation-done", args=[rec.id]), {"done": False}, format="json")

        rec.refresh_from_db()
        assert rec.completed_at is None

    def test_чужую_рекомендацию_отметить_нельзя(self, client_family):
        family, _, member = client_family
        _, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        rec = self._make_rec(family, prof, member)
        stranger = User.objects.create_user(email="other@example.com", name="Чужой", password="pass12345")
        other_family = Family.objects.create(owner=stranger, name="Чужая семья")
        FamilyMember.objects.create(family=other_family, user=stranger, role=FamilyMember.Role.HEAD)

        r = api(stranger).post(reverse("my-recommendation-done", args=[rec.id]), {}, format="json")

        assert r.status_code == 404
        rec.refresh_from_db()
        assert rec.completed_at is None

    def test_специалист_видит_отметку_выполнения(self, client_family):
        family, user, member = client_family
        trainer_user, prof = make_specialist("trainer@example.com", Specialist.Type.TRAINER)
        assign(prof, family)
        rec = self._make_rec(family, prof, member)
        api(user).post(reverse("my-recommendation-done", args=[rec.id]), {}, format="json")

        r = api(trainer_user).get(reverse("cabinet-recommendations", args=[family.id]))

        assert r.data[0]["completed_at"] is not None
