"""MG_HEADKEEPS: кто может вести дневник участника семьи.

Одно место на весь проект — как `family/selection.py` для выбора семьи. Правило
про чужие личные записи, и разъехавшись копиями, оно однажды разойдётся в
сторону «можно»: приватность ломается тихо, о ней не приходит отчёт об ошибке.

Правил ровно два, и они про разные действия.

**Добавить** запись за участника глава семьи может всегда. Запись достаётся
участнику, но помечена тем, кто её внёс (`added_by`), и в списке видна короной.
Ничего чужого при этом не переписывается: была одна строка, стало две.

**Править и удалять** чужое — только когда участник это разрешил
(`profile.head_may_edit_diary`) или когда он несовершеннолетний. У ребёнка
дневник ведут родители, ждать от него галочки бессмысленно. Возраст считается
по `birth_year`; год не указан — считаем взрослым: обратное открывало бы чужой
дневник по умолчанию, а умолчание в вопросах приватности должно быть строгим.

Своё — всегда и без оговорок: обе функции пропускают владельца первым же
условием.

Специалистов это не касается: у них свой доступ к клиенту и свои ручки, и
смешивать два разных вопроса в одном правиле не нужно.
"""

import datetime

from apps.family.models import FamilyMember

# Совершеннолетие. Вынесено в имя, чтобы в коде не стояло голое 18 без
# объяснения, что это и почему сравнивается именно так.
ADULT_AGE = 18


def _age(profile):
    """Полных лет по году рождения. None — если год неизвестен."""
    year = getattr(profile, "birth_year", None)
    if not year:
        return None
    # По году, а не по дате: дня рождения мы не спрашиваем. Значит, человек
    # считается взрослым с 1 января года, в котором ему исполняется 18, — на
    # несколько месяцев раньше правды. Ошибка тут в сторону строгости: чужой
    # дневник закрывается раньше, а не открывается дольше положенного.
    return datetime.date.today().year - int(year)


def is_minor(user):
    """Несовершеннолетний ли. Неизвестный возраст — считаем взрослым."""
    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    age = _age(profile)
    return age is not None and age < ADULT_AGE


def _is_head_of(current, target):
    """Глава ли `current` в той же семье, где состоит `target`."""
    if current is None or target is None:
        return False
    if current.family_id != target.family_id:
        return False
    return current.role == FamilyMember.Role.HEAD


def can_add_for(current, target):
    """Может ли `current` внести запись за `target`. См. шапку файла."""
    if current is None or target is None:
        return False
    if current.user_id == target.user_id:
        return True
    return _is_head_of(current, target)


def can_edit_of(current, target):
    """Может ли `current` править и удалять записи `target`. См. шапку файла."""
    if current is None or target is None:
        return False
    if current.user_id == target.user_id:
        return True
    if not _is_head_of(current, target):
        return False
    if is_minor(target.user):
        return True
    profile = getattr(target.user, "profile", None)
    return bool(getattr(profile, "head_may_edit_diary", False))


def can_change_row(current, target, row):
    """Может ли `current` переписать или удалить УЖЕ СУЩЕСТВУЮЩУЮ строку.

    Вода, вес и обхваты хранятся по одной строке на дату: повторная запись за
    тот же день не добавляет вторую точку, а правит первую. Значит, вторая
    запись за занятый день — это правка чужого, а не добавление, и разрешение
    для неё нужно то же, что для правки записи дневника.

    Без этой проверки правило разъезжалось: запись дневника глава без согласия
    поправить не мог, а вес участника — молча перезаписывал, потому что POST
    выглядел как «добавить».

    Исключение то же, что у дневника: строку, которую внёс сам `current`, он
    правит и убирает без разрешения — иначе его собственная ошибка осталась бы
    у человека навсегда.

    `row is None` — строки за эту дату ещё нет, это добавление: см.
    `can_add_for`.
    """
    if row is None:
        return can_add_for(current, target)
    if current is None or target is None:
        return False
    if getattr(row, "added_by_id", None) and row.added_by_id == current.user_id:
        return True
    return can_edit_of(current, target)


def author_for(current, target):
    """Что писать в `added_by`: автора, если он не владелец, иначе ничего.

    Пустое поле у своей записи — не небрежность, а смысл: «внёс сам». Так
    выглядят все записи, сделанные до этой задачи, и разбирать их отдельно
    клиенту не нужно.
    """
    if current is None or target is None:
        return None
    if current.user_id == target.user_id:
        return None
    return current.user
