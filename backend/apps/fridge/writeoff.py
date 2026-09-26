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

MG_UNITNORM: одной арифметики мало. Холодильник хранит покупку («яйца 30 шт»),
рецепт считает граммами, и эти две правды не встречались вовсе — позиция уходила
в нехватку, сколько бы её дома ни лежало. Перевод между ними лежит в
`apps/fridge/units.py` и зовётся отсюда и из `_subtract_fridge`. Работает он
только по явной записи о весе единицы: нет записи — нет перевода, и всё ведёт
себя как раньше.
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


def _dish_key(menu_item):
    """Ключ события: блюдо в меню, а не отметка человека.

    Уникальность в базе на этот ключ есть только при заполненном `menu`, и
    Postgres считает NULL-ы различными — у блюда-продукта `recipe_id` пуст.
    Поэтому повторное списание ловится не ограничением, а поиском по этому же
    ключу перед записью.
    """
    return {
        "family": menu_item.menu.family,
        "menu_id": menu_item.menu_id,
        "day_offset": menu_item.day_offset,
        "meal_slot": menu_item.meal_slot or menu_item.meal_type or "",
        "recipe_id": menu_item.recipe_id,
    }


def find_write_off(menu_item):
    """Списание этого блюда, если оно уже было. Иначе None."""
    return FridgeWriteOff.objects.filter(**_dish_key(menu_item)).first()


@transaction.atomic
def write_off_menu_item(menu_item, *, user_id=None):
    """Списать продукты блюда. Возвращает (событие, создано ли оно сейчас).

    Повторный вызов для того же блюда ничего не меняет: списание уже есть.
    """
    from apps.shopping.services import _fr_base, _fr_unit_factor

    family = menu_item.menu.family
    key = _dish_key(menu_item)
    existing = FridgeWriteOff.objects.filter(**key).first()
    if existing is not None:
        return existing, False

    from apps.fridge.aliases import product_ref_index
    from apps.fridge.units import to_grams, unit_weight_index

    pidx = product_ref_index()
    rows = _fridge_rows(family)
    needs = [n for n in _need_rows(menu_item) if n.get("quantity") is not None]

    state = []
    for it in rows:
        dim, base = _fr_base(it.quantity, it.unit)
        _, factor = _fr_unit_factor(it.unit)
        pid, canon = _match_key(it.name, it.product_id, pidx)
        state.append(
            {"item": it, "dim": dim, "base": base, "factor": factor, "pid": pid, "canon": canon, "g_per_base": None}
        )

    # MG_UNITNORM: справочник весов — одним запросом на всё блюдо, а не по
    # запросу на позицию: в недельном меню позиций под сотню.
    need_keys = [_match_key(n.get("name"), n.get("product_id"), pidx)[0] for n in needs]
    # MG_FAMWEIGHT: вес этой семьи важнее общего — своя пачка творога, а не
    # усреднённая по каталогу.
    widx = unit_weight_index([s["pid"] for s in state] + need_keys, family=family)

    for s in state:
        # Сколько граммов в одной единице БАЗЫ (г для массы, мл для объёма,
        # штука для штук). Считаем общим переводом, чтобы не разбирать каждую
        # единицу отдельно: «1 л = 1030 г» превращается здесь в «1.03 г на мл»
        # сам собой.
        mass_total = to_grams(s["item"].quantity, s["item"].unit, s["pid"], widx)
        if mass_total is not None and s["base"]:
            s["g_per_base"] = mass_total / s["base"]

    write_off = FridgeWriteOff.objects.create(reason=FridgeWriteOff.Reason.COOKED, created_by_id=user_id, **key)

    for need in needs:
        qty = need.get("quantity")
        need_dim, need_factor = _fr_unit_factor(need.get("unit"))
        try:
            need_qty = qty if isinstance(qty, Decimal) else Decimal(str(qty))
        except Exception:
            continue

        pid, canon = _match_key(need.get("name"), need.get("product_id"), pidx)
        need_mass = to_grams(need_qty, need.get("unit"), pid, widx)

        # MG_UNITNORM: если потребность переводится в граммы, считаем в них —
        # тогда «яйца 30 шт» в холодильнике закрывают «Яйца куриные 50 г» в
        # рецепте. Раньше такие строки не встречались вовсе: размерности
        # разные, и позиция молча уходила в нехватку.
        #
        # Если веса нет ни у одной стороны, работаем как раньше — по
        # совпадению размерности. Догадываться о весе нельзя: неверная цифра
        # унесёт из холодильника не то количество, и человек узнает об этом,
        # только открыв дверцу.
        in_grams = need_mass is not None
        if in_grams:
            remaining = need_mass
            candidates = [s for s in state if s["base"] and s["g_per_base"]]
            per_need_unit = need_mass / need_qty if need_qty else Decimal(1)
        else:
            remaining = need_qty * need_factor
            candidates = [s for s in state if s["base"] and s["dim"] == need_dim]
            per_need_unit = need_factor

        matches = [s for s in candidates if pid and s["pid"] == pid]
        if not matches:
            matches = [s for s in candidates if canon and s["canon"] == canon]

        for s in matches:
            if remaining <= 0:
                break
            g_per_base = s["g_per_base"] if in_grams else Decimal(1)
            available = s["base"] * g_per_base
            take = min(available, remaining)
            remaining -= take
            take_base = take / g_per_base
            s["base"] -= take_base
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
                quantity=(take_base / s["factor"]) if s["factor"] else take_base,
                unit=item.unit,
            )

        if remaining > 0:
            FridgeWriteOffLine.objects.create(
                write_off=write_off,
                fridge_item=None,
                product_id=need.get("product_id"),
                name=need.get("name") or "",
                shortfall=(remaining / per_need_unit) if per_need_unit else remaining,
                shortfall_unit=need.get("unit") or "",
            )

    return write_off, True


@transaction.atomic
def write_off_fridge_item(item, quantity=None, *, user_id=None):
    """Ручное списание: человек израсходовал позицию сам, без блюда из меню.

    Количество — в единице самой позиции, и ни во что не переводится. Перевод
    (MG_UNITNORM) нужен там, где встречаются две разные правды: рецепт в
    граммах и холодильник в штуках. Здесь правда одна — человек смотрит на
    конкретную пачку и говорит, сколько ушло из НЕЁ. Переводить это в граммы и
    обратно значило бы гонять число через справочник без всякой нужды, теряя на
    округлении.

    `quantity=None` — израсходовано всё. Больше, чем лежит, списать нельзя:
    остаток обрезается, иначе холодильник ушёл бы в минус.
    """
    available = item.quantity or Decimal(0)
    take = available if quantity is None else Decimal(str(quantity))
    if take <= 0:
        raise ValueError("Количество должно быть больше нуля.")
    take = min(take, available)

    write_off = FridgeWriteOff.objects.create(
        family=item.family,
        reason=FridgeWriteOff.Reason.MANUAL,
        created_by_id=user_id,
    )
    FridgeWriteOffLine.objects.create(
        write_off=write_off,
        fridge_item=item,
        product_id=item.product_id,
        name=item.name,
        quantity=take,
        unit=item.unit,
    )

    item.quantity = available - take
    if item.quantity <= 0:
        item.quantity = Decimal(0)
        item.is_deleted = True
    item.save(update_fields=["quantity", "is_deleted", "updated_at"])
    return write_off


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
    """Чего не хватило — для экрана «докупил».

    Отбор идёт по `shortfall`, а не по пустому `fridge_item`: позицию
    холодильника могут удалить, связь тогда обнуляется (SET_NULL), и списанная
    строка притворилась бы нехваткой.
    """
    return list(write_off.lines.filter(shortfall__isnull=False))


def write_off_payload(write_off):
    """Что показать человеку после «приготовил»: что ушло и чего не хватило.

    Числа отдаём строками — так же, как их отдаёт DRF для Decimal в остальных
    ручках: иначе мобильный клиент получит в одном месте число, в другом
    строку и разберёт их по-разному.
    """
    written, missing = [], []
    for line in write_off.lines.all():
        if line.shortfall is not None:
            missing.append(
                {
                    "name": line.name,
                    "product_id": line.product_id,
                    "quantity": str(line.shortfall),
                    "unit": line.shortfall_unit,
                }
            )
        elif line.quantity is not None:
            written.append(
                {
                    "name": line.name,
                    "product_id": line.product_id,
                    "fridge_item_id": line.fridge_item_id,
                    "quantity": str(line.quantity),
                    "unit": line.unit,
                }
            )
    return {
        "write_off_id": write_off.id,
        "written_off": written,
        "shortfall": missing,
    }
