"""MG_ONEFAMILY: сторож — правило выбора семьи объявлено ровно в одном месте.

Зачем нужен отдельный тест на текст исходников. Задача T-25 свела восемь копий
правила в `apps/family/selection.py`, но копий оказалось десять: две нашлись уже
на проде, после выкатки. Первую — в кабинете специалиста — заметить было негде,
вторая стоила видимого сбоя: человек переключился в семью с премиумом, всё
приложение показывало премиум, а страница «Подписка» — свой бесплатный тариф,
потому что подписки спрашивали семью своей копией правила. Та же функция
выбирает семью при оплате, то есть платёж мог уйти не в ту семью.

Причина промаха проста и повторяема: копии искали глазами по выводу grep, а
вывод был обрезан. Поэтому проверку и стоит доверить не глазам.

Тест ловит выражения вида `FamilyMember.objects...first()` — способ достать
«одно членство пользователя», то есть ровно ту заготовку, из которой вырастает
очередная копия. Списки всех семей человека (`values_list("family_id")`) он не
трогает: это другой вопрос — «в каких семьях человек состоит вообще», и ответ на
него законно не зависит от выбранной семьи.

Если тест упал на новом коде — не обходите его правкой списка исключений:
скорее всего, вам нужен `current_family()` или `current_membership()`.
"""

import pathlib
import re

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[3]
APPS_ROOT = BACKEND_ROOT / "apps"

# Единственное место, где правило имеет право быть.
ALLOWED = {
    APPS_ROOT / "family" / "selection.py",
}

# «Достать одно членство пользователя»: FamilyMember.objects…filter(user=…)…first()
PATTERN = re.compile(
    r"FamilyMember\.objects[^\n]*\.filter\(\s*user(?:_id)?\s*=[^\n]*\)[^\n]*\.first\(\)",
)


def _sources():
    for path in APPS_ROOT.rglob("*.py"):
        parts = set(path.parts)
        if "migrations" in parts or "tests" in parts or "__pycache__" in parts:
            continue
        yield path


def test_only_selection_module_resolves_the_current_family():
    offenders = []
    for path in _sources():
        if path in ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PATTERN.search(line):
                offenders.append(f"{path.relative_to(BACKEND_ROOT)}:{number}: {line.strip()}")

    assert not offenders, (
        "Правило выбора семьи продублировано. Используйте current_family() или "
        "current_membership() из apps/family/selection.py:\n  " + "\n  ".join(offenders)
    )
