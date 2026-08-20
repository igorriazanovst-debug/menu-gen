"""MG_PRODFAMILY: развести общий каталог и продукты семей.

Два переноса, оба идемпотентны и оба ничего не делают на пустой базе (тесты).

1. Продукты с владельцем-пользователем становятся продуктами его семьи.
   Раньше `owner` определял видимость; теперь — только авторство.

2. Продукты без владельца, которые на самом деле вписал пользователь в свой
   список покупок, отдаются его семье. Признак: на продукт ссылаются позиции
   списков ровно одной семьи, он не seed, у него нет штрихкода и он не связан
   ни с одним рецептом. Такие в общий каталог попали по ошибке — это они
   выглядят как «прокладки Белла ночные» в справочнике продуктов у всех.

Неоднозначное не трогаем: если на продукт ссылаются списки разных семей,
владельца не угадать — он остаётся в каталоге.
"""

from django.db import migrations


def to_families(apps, schema_editor):
    Product = apps.get_model("fridge", "Product")
    FamilyMember = apps.get_model("family", "FamilyMember")
    ShoppingListItem = apps.get_model("shopping", "ShoppingListItem")

    # 1) владелец-пользователь → его семья
    family_by_user = dict(FamilyMember.objects.values_list("user_id", "family_id"))
    moved = 0
    for pid, owner_id in Product.objects.filter(owner__isnull=False, owner_family__isnull=True).values_list(
        "id", "owner_id"
    ):
        fam_id = family_by_user.get(owner_id)
        if fam_id:
            Product.objects.filter(id=pid).update(owner_family_id=fam_id)
            moved += 1

    # 2) «каталожные» продукты, пришедшие из списков покупок
    candidates = Product.objects.filter(
        owner_family__isnull=True,
        is_seed=False,
        barcode__isnull=True,
        recipe_links__isnull=True,
    ).values_list("id", flat=True)
    claimed = 0
    for pid in set(candidates):
        fam_ids = set(
            ShoppingListItem.objects.filter(product_id=pid).values_list("shopping_list__family_id", flat=True)
        )
        fam_ids.discard(None)
        if len(fam_ids) == 1:
            Product.objects.filter(id=pid).update(owner_family_id=fam_ids.pop())
            claimed += 1

    if moved or claimed:
        print(f"  MG_PRODFAMILY: перенесено по владельцу {moved}, опознано по спискам покупок {claimed}")


def back(apps, schema_editor):
    """Вернуть всё в каталог. Обратный ход не восстанавливает прежний вид
    каталога дословно, но и не теряет данных — продукты остаются на месте."""
    Product = apps.get_model("fridge", "Product")
    Product.objects.filter(owner_family__isnull=False).update(owner_family=None)


class Migration(migrations.Migration):
    dependencies = [
        ("fridge", "0016_product_owner_family_alter_product_owner_and_more"),
        # 0003 добавил ShoppingListItem.product — по нему и опознаём владельца.
        ("shopping", "0003_shoppinglistitem_category_fk_and_more"),
        ("family", "0001_initial"),
        # 0015 создал RecipeProduct: без него в состоянии миграций не разрешится
        # обратная связь recipe_links, по которой отсеиваются продукты рецептов.
        ("recipes", "0015_recipeproduct"),
    ]

    operations = [migrations.RunPython(to_families, back)]
