"""MG_CONSTRUCTORACCESS: специалист строит меню только своим клиентам.

Конструктор жил по своему правилу доступа, отличному от кабинета: staff видел
все семьи, список включал PENDING, а привязку меню к семье (client_family)
никто не проверял. Итог — специалист (и тем более админ с профилем
специалиста) видел чужие семьи и мог привязать меню к любой из них по
произвольному id.

Теперь одно правило и на список, и на запись: только семьи с активным
назначением — то же, что даёт доступ к данным клиента.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.family.models import Family, FamilyMember
from apps.menu.models import ConstructedMenu
from apps.specialists.models import Specialist, SpecialistAssignment
from apps.users.models import User


@pytest.fixture
def specialist(db):
    user = User.objects.create_user(email="diet@example.com", password="pass12345", name="Диетолог")
    prof = Specialist.objects.create(user=user, specialist_type=Specialist.Type.DIETITIAN, is_verified=True)
    return user, prof


def make_family(name):
    owner = User.objects.create_user(email=f"{name}@example.com", password="pass12345", name=name)
    family = Family.objects.create(name=f"Семья {name}", owner=owner)
    FamilyMember.objects.create(family=family, user=owner, role="adult")
    return family


def assign(prof, family, status=SpecialistAssignment.Status.ACTIVE):
    return SpecialistAssignment.objects.create(
        family=family, specialist=prof, specialist_type=prof.specialist_type, status=status
    )


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.mark.django_db
class TestClientList:
    def test_виден_только_клиент_с_активным_назначением(self, specialist):
        user, prof = specialist
        mine = make_family("mine")
        assign(prof, mine)
        make_family("stranger")  # чужая семья, без назначения

        r = api(user).get(reverse("constructor-clients"))

        assert r.status_code == 200
        assert [f["id"] for f in r.data] == [mine.id]

    def test_pending_не_показывается(self, specialist):
        """PENDING не даёт доступа к данным — не должен и в конструкторе."""
        user, prof = specialist
        pending = make_family("pending")
        assign(prof, pending, status=SpecialistAssignment.Status.PENDING)

        r = api(user).get(reverse("constructor-clients"))

        assert r.data == []

    def test_завершённое_назначение_убирает_из_списка(self, specialist):
        user, prof = specialist
        ex = make_family("ex")
        assign(prof, ex, status=SpecialistAssignment.Status.ENDED)

        r = api(user).get(reverse("constructor-clients"))

        assert r.data == []

    def test_админ_не_видит_все_семьи(self, db):
        """Даже staff с профилем специалиста видит только своих клиентов."""
        admin = User.objects.create_user(email="admin@example.com", password="pass12345", name="Админ", is_staff=True)
        Specialist.objects.create(user=admin, specialist_type=Specialist.Type.DIETITIAN, is_verified=True)
        make_family("someone")  # есть семья, но назначения админу нет

        r = api(admin).get(reverse("constructor-clients"))

        assert r.status_code == 200
        assert r.data == []


@pytest.mark.django_db
class TestBindMenuToFamily:
    def _payload(self, family_id=None):
        data = {"name": "Меню", "days": 1, "status": "draft", "meals": []}
        if family_id is not None:
            data["client_family"] = family_id
        return data

    def test_меню_привязывается_к_своему_клиенту(self, specialist):
        user, prof = specialist
        mine = make_family("mine")
        assign(prof, mine)

        r = api(user).post(reverse("constructor-list"), self._payload(mine.id), format="json")

        assert r.status_code == 201, r.data
        assert ConstructedMenu.objects.get().client_family_id == mine.id

    def test_привязка_к_чужой_семье_отклоняется(self, specialist):
        """Дыра на записи: фильтр списка чужой id не останавливал."""
        user, prof = specialist
        assign(prof, make_family("mine"))
        alien = make_family("alien")  # не клиент этого специалиста

        r = api(user).post(reverse("constructor-list"), self._payload(alien.id), format="json")

        assert r.status_code == 400
        assert "клиент" in str(r.data).lower()
        assert not ConstructedMenu.objects.exists()

    def test_шаблон_без_семьи_разрешён(self, specialist):
        """Меню без client_family — заготовка, не привязанная ни к кому."""
        user, _ = specialist

        r = api(user).post(reverse("constructor-list"), self._payload(None), format="json")

        assert r.status_code == 201, r.data
        assert ConstructedMenu.objects.get().client_family_id is None

    def test_переприязка_к_чужой_при_обновлении_отклоняется(self, specialist):
        user, prof = specialist
        mine = make_family("mine")
        assign(prof, mine)
        alien = make_family("alien")
        menu = ConstructedMenu.objects.create(author=user, name="Меню", client_family=mine, days=1)

        r = api(user).patch(
            reverse("constructor-detail", args=[menu.id]),
            {"client_family": alien.id, "meals": []},
            format="json",
        )

        assert r.status_code == 400
        menu.refresh_from_db()
        assert menu.client_family_id == mine.id
