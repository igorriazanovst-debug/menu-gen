"""MG_ONEFAMILY: на вопрос «в какой семье пользователь» отвечает одно место.

Что это чинит (замер на проде, chat-84). Вопрос решался восемью независимыми
копиями, шесть смотрели сначала на членство, две — сначала на владение семьёй, и
все брали `.first()` у запроса без сортировки. Выглядело как лотерея, а на деле
Django неотсортированному запросу сам добавляет `order_by("pk")`: побеждало самое
старое членство. Своя семья заводится при регистрации, значит её членство всегда
старше приглашения, полученного позже, — и приглашение существующего аккаунта не
работало ни у кого и никогда.

Главное, что здесь проверяется, — не «какая именно семья», а что **все девять
точек называют одну и ту же**. Пока они расходятся, переключение семьи (T-26)
невозможно: человек получит холодильник одной семьи со списком покупок другой.

Имена выдуманные: в тестовой базе есть посевной каталог продуктов (миграция
fridge 0004), но не семьи.
"""

import pytest

from apps.diary.views import _get_member as diary_member
from apps.family.models import Family, FamilyMember
from apps.family.selection import current_family, current_membership
from apps.family.views import _get_user_family as family_screen
from apps.fridge.views import _get_family as fridge
from apps.fridge.visibility import family_of as product_catalog
from apps.menu.views import _get_family as menu
from apps.payments.views import _get_family as payments
from apps.shopping.permissions import get_user_family as shopping
from apps.subscriptions.permissions import get_user_family as subscriptions
from apps.users.deletion_views import _family_of as account_deletion
from apps.users.models import User

# Восемь точек, которые отвечают семьёй. Девятая (дневник) отвечает членством и
# проверяется отдельно — у неё другой тип результата.
FAMILY_RESOLVERS = [
    ("экран Семья", family_screen),
    ("холодильник", fridge),
    ("каталог продуктов", product_catalog),
    ("меню", menu),
    ("платежи", payments),
    ("подписка", subscriptions),
    ("покупки", shopping),
    ("удаление аккаунта", account_deletion),
]


def _user(email, name):
    return User.objects.create_user(email=email, name=name, password="pass1234")


def _family_with_head(user, name):
    family = Family.objects.create(owner=user, name=name)
    FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return family


def _all_answers(user):
    """Что ответит каждая точка. Ключ — человекочитаемое имя точки."""
    return {label: fn(user) for label, fn in FAMILY_RESOLVERS}


@pytest.mark.django_db
def test_one_membership_all_points_agree():
    user = _user("odna@example.test", "Одна семья")
    family = _family_with_head(user, "Семья Первая")

    answers = _all_answers(user)
    assert set(answers.values()) == {family}, answers
    assert current_family(user) == family


@pytest.mark.django_db
def test_two_memberships_all_points_agree():
    """Ровно случай, из-за которого приглашение не работало.

    Человек состоит в двух семьях: своей (заведена раньше) и той, куда его
    пригласили. Какая победит — предмет T-26; здесь важно только то, что все
    девять точек называют ОДНУ и ту же.
    """
    user = _user("dve@example.test", "Две семьи")
    own = _family_with_head(user, "Семья Своя")
    invited = Family.objects.create(owner=_user("glava@example.test", "Глава"), name="Семья Пригласившая")
    FamilyMember.objects.create(family=invited, user=user, role=FamilyMember.Role.MEMBER)

    answers = _all_answers(user)
    assert len(set(answers.values())) == 1, answers
    # Сегодняшнее поведение сохранено дословно: побеждает самое старое членство.
    assert set(answers.values()) == {own}
    assert invited not in answers.values()


@pytest.mark.django_db
def test_oldest_membership_wins_regardless_of_creation_order_of_families():
    """Решает возраст членства, а не возраст семьи.

    Семья пригласившего может быть заведена раньше — членство в ней всё равно
    появилось позже, и выигрывает своё.
    """
    stranger = _user("chuzhoy@example.test", "Чужой")
    older_family = _family_with_head(stranger, "Семья Старшая")

    user = _user("pozzhe@example.test", "Позже")
    own = _family_with_head(user, "Семья Поздняя")
    FamilyMember.objects.create(family=older_family, user=user, role=FamilyMember.Role.MEMBER)

    assert current_family(user) == own
    assert len(set(_all_answers(user).values())) == 1


@pytest.mark.django_db
def test_owner_without_membership_falls_back_to_owned_family():
    """Запасной путь: членство удалили руками, семья осталась.

    Раньше здесь копии расходились: шесть возвращали None, две — семью. Теперь
    все восемь отвечают одинаково.
    """
    user = _user("bez_chlenstva@example.test", "Без членства")
    family = Family.objects.create(owner=user, name="Семья Без Членства")

    answers = _all_answers(user)
    assert set(answers.values()) == {family}, answers
    assert current_membership(user) is None


@pytest.mark.django_db
def test_no_family_at_all_returns_none():
    user = _user("nikakoy@example.test", "Никакой")
    answers = _all_answers(user)
    assert set(answers.values()) == {None}, answers
    assert current_membership(user) is None


@pytest.mark.django_db
def test_diary_point_returns_the_same_family():
    """Девятая точка отвечает членством — семья у него должна быть той же."""
    user = _user("dnevnik@example.test", "Дневник")
    own = _family_with_head(user, "Семья Дневниковая")
    invited = Family.objects.create(owner=_user("hozyain@example.test", "Хозяин"), name="Семья Чужая")
    FamilyMember.objects.create(family=invited, user=user, role=FamilyMember.Role.MEMBER)

    membership = diary_member(user)
    assert membership is not None
    assert membership.family == own
    assert membership == current_membership(user)


@pytest.mark.django_db
def test_anonymous_user_gets_none():
    from django.contrib.auth.models import AnonymousUser

    assert current_family(AnonymousUser()) is None
    assert current_membership(AnonymousUser()) is None
    assert current_family(None) is None
    assert current_membership(None) is None
