"""MG_WRITEOFF: списание продуктов из холодильника.

Холодильник до сих пор только пополнялся: купленное перекладывалось в него из
списка покупок, а убирать приходилось руками. Съеденное в нём оставалось, и со
временем он расходился с реальностью — а на этом расхождении стоит список
покупок, который вычитает из потребности то, что лежит дома. Фарш, съеденный
неделю назад, честно вычитался и в список не попадал.

Правила, о которых договорились:

- **Сколько списывать** — ровно столько, сколько посчитал бы список покупок для
  этого блюда. Состав берётся тем же кодом (`build_items_for_menu_items`), и
  поэтому «купили» и «списали» не расходятся. Если бы списание считало иначе —
  например, делило рецепт на порции, — холодильник начал бы врать в другую
  сторону, и разобраться в этом было бы невозможно.

- **Событие привязано к блюду, а не к человеку.** Пункт меню принадлежит
  участнику семьи: одно блюдо на троих — три пункта, и «съел» отметят трое.
  Ключ события (меню, день, приём, рецепт) уникален, поэтому повторный вызов
  ничего не списывает и возвращает уже сделанное.

- **Нехватка — не повод гадать.** Списываем в ноль, остаток пишем строкой без
  позиции холодильника. Что с ним делать, решает человек кнопкой «докупил»: раз
  он отметил, что приготовил, значит нехватку он уже как-то закрыл.

- **Отмена возвращает ровно то, что ушло.** Поэтому в строке хранится
  количество в единице той позиции, из которой списали, а нехватка — в единице
  потребности.

Единицы считает та же арифметика, что и вычитание при сборке списка покупок
(`_fr_base`, `_fr_unit_factor`): граммы к килограммам, миллилитры к литрам,
штуки к штукам. Одно правило на оба конца — иначе список и холодильник
разъедутся на первом же «кг».
"""

from decimal import Decimal

from django.db import transaction

from apps.fridge.models import FridgeItem, FridgeWriteOff, FridgeWriteOffLine


def _need_rows(menu_item):
    """Что нужно для блюда — тем же кодом, что и список покупок."""
    from apps.shopping.services import build_items_for_menu_items

    family = menu_item.menu.family
    return build_items_for_menu_items([menu_item], family, subtract_fridge=False)


def _fridge_rows(family):
    """Позиции холодильника. Порядок — сначала то, что раньше испортится.

    Списывать надо из той пачки, что скиснет первой: иначе человек будет
    доставать свежее, а приложение — считать, что съедено старое.
    """
    rows = list(FridgeItem.objects.filter(family=family, is_deleted=False))
    rows.sort(key=lambda it: (it.expiry_date is None, it.expiry_date, it.id))
    return rows


def _match_key(name, product_id, pidx):
    """Ключ сопоставления: номер товара, иначе каноничное имя через синонимы."""
    from apps.fridge.aliases import normalize_alias, resolve_ref
    from apps.shopping.services import _fr_canon

    ref = resolve_ref(name, pidx)
    pid = product_id or (ref["id"] if ref else None)
    canon = normalize_alias(ref["name"]) if ref else _fr_canon(name)
    return pid, canon


@transaction.atomic
def write_off_menu_item(menu_item, *, user_id=None):
    """Списать продукты блюда. Возвращает (событие, создано ли оно сейчас).

    Повторный вызов для того же блюда ничего не меняет: списание уже есть.
    """
    from apps.shopping.services import _fr_base, _fr_unit_factor

    family = menu_item.menu.family
    key = {
        "family": family,
        "menu_id": menu_item.menu_id,
        "day_offset": menu_item.day_offset,
        "meal_slot": menu_item.meal_slot or menu_item.meal_type or "",
        "recipe_id": menu_item.recipe_id,
    }
    existing = FridgeWriteOff.objects.filter(**key).first()
    if existing is not None:
        return existing, False

    from apps.fridge.aliases import product_ref_index

    pidx = product_ref_index()
    rows = _fridge_rows(family)
    state = []
    for it in rows:
        dim, base = _fr_base(it.quantity, it.unit)
        _, factor = _fr_unit_factor(it.unit)
        pid, canon = _match_key(it.name, it.product_id, pidx)
        state.append({"item": it, "dim": dim, "base": base, "factor": factor, "pid": pid, "canon": canon})

    write_off = FridgeWriteOff.objects.create(reason=FridgeWriteOff.Reason.COOKED, created_by_id=user_id, **key)

    for need in _need_rows(menu_item):
        qty = need.get("quantity")
        if qty is None:
            # Потребность без числа («Соль») списывать не из чего: сколько её
            # ушло, не знает никто. Такие строки просто пропускаем.
            continue
        need_dim, need_factor = _fr_unit_factor(need.get("unit"))
        try:
            remaining = (qty if isinstance(qty, Decimal) else Decimal(str(qty))) * need_factor
        except Exception:
            continue

        pid, canon = _match_key(need.get("name"), need.get("product_id"), pidx)
        matches = [s for s in state if s["base"] and s["dim"] == need_dim and pid and s["pid"] == pid]
        if not matches:
            matches = [s for s in state if s["base"] and s["dim"] == need_dim and canon and s["canon"] == canon]

        for s in matches:
            if remaining <= 0:
                break
            take = min(s["base"], remaining)
            remaining -= take
            s["base"] -= take
            item = s["item"]
            item.quantity = (s["base"] / s["factor"]) if s["factor"] else s["base"]
            if item.quantity <= 0:
                item.quantity = Decimal(0)
                item.is_deleted = True
            item.save(update_fields=["quantity", "is_deleted", "updated_at"])
            FridgeWriteOffLine.objects.create(
                write_off=write_off,
                fridge_item=item,
                product_id=item.product_id,
                name=item.name,
                quantity=(take / s["factor"]) if s["factor"] else take,
                unit=item.unit,
            )

        if remaining > 0:
            FridgeWriteOffLine.objects.create(
                write_off=write_off,
                fridge_item=None,
                product_id=need.get("product_id"),
                name=need.get("name") or "",
                shortfall=(remaining / need_factor) if need_factor else remaining,
                shortfall_unit=need.get("unit") or "",
            )

    return write_off, True


@transaction.atomic
def undo_write_off(write_off):
    """Вернуть в холодильник ровно то, что ушло, и убрать запись."""
    for line in write_off.lines.select_related("fridge_item"):
        item = line.fridge_item
        if item is None or line.quantity is None:
            continue  # строка нехватки: возвращать нечего
        item.quantity = (item.quantity or Decimal(0)) + line.quantity
        item.is_deleted = False
        item.save(update_fields=["quantity", "is_deleted", "updated_at"])
    write_off.delete()


def shortfall_lines(write_off):
    """Чего не хватило — для экрана «докупил»."""
    return list(write_off.lines.filter(fridge_item__isnull=True))
