"""MG_PRODFAMILY: кто какие продукты видит. Одно правило на все входы.

Каталог (`owner_family IS NULL`) — общий и неизменный: он один на всех,
правится только через админку и не растёт от пользовательского ввода.
Продукт с семьёй виден участникам этой семьи и больше никому.

Правило живёт здесь, а не в каждом view, ровно потому, что прошлый раз оно
жило в `fridge/views.py` — и рубрикатор списка покупок, который про него не
знал, показывал чужие продукты всем подряд.
"""

from django.db.models import Q

from apps.family.models import FamilyMember


def family_of(user):
    """Семья пользователя. None — если он ни в одной не состоит."""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    membership = FamilyMember.objects.select_related("family").filter(user=user).first()
    return membership.family if membership else None


# MG_SCANSRC: продукт, «опознанный» моделью по штрих-коду, когда его не нашлось
# в OpenFoodFacts. Проверить такую запись нечем, поэтому в списки, где выбирают
# продукт (дневник, покупки, конструктор меню), она не попадает: там её увидели
# бы как обычный справочный продукт и поверили бы КБЖУ.
#
# Из базы её при этом не убираем — позиция холодильника ссылается на неё по FK,
# и повторный скан того же кода должен находить её, а не ходить в сеть заново.
UNVERIFIED_SOURCES = ("ai",)  # = Product.Source.AI, строкой — модуль не тянет модели fridge


def _verified():
    return ~Q(source__in=UNVERIFIED_SOURCES)


def family_products_q(family):
    """Продукты конкретной семьи — без оговорок про происхождение.

    Свой продукт семья добавила сама и отвечает за него сама.
    """
    return Q(owner_family=family)


def visible_products_q(user=None, family=None):
    """Условие видимости: общий каталог + продукты своей семьи.

    Пользователь без семьи видит только каталог — как и любой посторонний.
    """
    if family is None:
        family = family_of(user)
    if family is None:
        return catalog_q()
    return catalog_q() | family_products_q(family)


def catalog_q():
    """Только общий каталог — для того, что по смыслу общее.

    Рецепты, синонимы и сопоставление ингредиентов работают с каталогом:
    привязать ингредиент рецепта к «Маминой настойке» одной семьи значило бы
    протащить её в чужие меню.
    """
    return Q(owner_family__isnull=True) & _verified()
