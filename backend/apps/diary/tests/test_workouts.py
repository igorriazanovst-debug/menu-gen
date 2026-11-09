"""MG_WORKOUT: физнагрузки в дневнике.

Заведено ради тренерской оптики: тренер видел в дневнике одну еду, а вопрос
«что человек делал на этом калораже» ответа не имел.

Главное, что проверяется здесь, — чего мы НЕ делаем. Расход не вычитается из
дневной нормы: норма уже содержит коэффициент активности («умеренные нагрузки
3–5 раз в неделю» — это множитель 1,55 в профиле), и прибавка за каждую
тренировку посчитала бы её дважды. Человеку на похудении приложение разрешило
бы съесть лишние полтысячи калорий — это работа против его цели, а не мелкая
неточность.

Названия и адреса выдуманные.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.diary.models import ActivityType, WeightLog, WorkoutLog
from apps.diary.workout_calories import burned_kcal, latest_weight_kg
from apps.family.models import Family, FamilyMember
from apps.users.models import Profile, User


def _person(email="sport@example.com", name="Спортсмен"):
    user = User.objects.create_user(email=email, password="x", name=name)
    Profile.objects.create(user=user, birth_year=1990)
    family = Family.objects.create(name="Семья", owner=user)
    member = FamilyMember.objects.create(family=family, user=user, role=FamilyMember.Role.HEAD)
    return user, member


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


class TestФормулаРасхода:
    """Формула без базы: MET × 3,5 × вес × минуты / 200."""

    def test_бег_час_при_семидесяти_килограммах(self):
        # MET 9.8 × 3.5 × 70 × 60 / 200 = 720 ккал. Сверяется с любым
        # калькулятором — числа не наши, а общепринятые.
        assert burned_kcal(Decimal("9.8"), Decimal("70"), 60) == 720

    def test_ходьба_полчаса(self):
        # 3.5 × 3.5 × 70 × 30 / 200 = 128,625 — округляется до 129.
        # Доли килокалории в дневнике не значат ничего и создают вид
        # точности, которой у формулы нет.
        assert burned_kcal(Decimal("3.5"), Decimal("70"), 30) == 129

    def test_без_веса_не_считаем(self):
        # Вес входит множителем. Подставить «среднего человека» значит
        # ошибиться на четверть в любую сторону — честнее не считать вовсе.
        assert burned_kcal(Decimal("9.8"), None, 60) is None

    def test_без_времени_и_без_коэффициента_тоже(self):
        assert burned_kcal(Decimal("9.8"), Decimal("70"), 0) is None
        assert burned_kcal(None, Decimal("70"), 60) is None

    def test_нелепое_значение_обрезается(self):
        # Сутки бега дали бы 17 тысяч. Такое в сводке дня — мусор, который
        # заметнее любой пользы.
        assert burned_kcal(Decimal("9.8"), Decimal("70"), 1440) == 5000


@pytest.mark.django_db
class TestПоследнийВес:
    def test_замер_важнее_профиля(self):
        # В профиле вес перезаписывается и может быть годовалым, в дневнике —
        # точка с датой.
        user, _ = _person()
        user.profile.weight_kg = Decimal("90")
        user.profile.save(update_fields=["weight_kg"])
        WeightLog.objects.create(user=user, date=date.today(), weight_kg=Decimal("78.25"))

        assert latest_weight_kg(user) == Decimal("78.25")

    def test_без_замеров_берём_профиль(self):
        user, _ = _person()
        user.profile.weight_kg = Decimal("90")
        user.profile.save(update_fields=["weight_kg"])

        assert latest_weight_kg(user) == Decimal("90")


@pytest.mark.django_db
class TestЗаписьЗанятия:
    def _activity(self, code="running_moderate"):
        return ActivityType.objects.get(code=code)

    def test_справочник_засеян_миграцией(self):
        # Значения из Compendium of Physical Activities. Если справочник пуст,
        # выбор занятия в приложении будет пустым списком.
        assert ActivityType.objects.filter(is_active=True).count() >= 40
        assert self._activity().met == Decimal("9.8")

    def test_расход_считается_сам(self):
        user, _ = _person()
        WeightLog.objects.create(user=user, date=date.today(), weight_kg=Decimal("70"))

        r = _client(user).post(
            reverse("diary-workouts"),
            {"date": str(date.today()), "activity": self._activity().id, "duration_min": 60},
            format="json",
        )

        assert r.status_code == 201, r.data
        assert r.data["calories"] == 720
        # Клиенту важно знать, что это наша оценка, а не показание прибора.
        assert r.data["calories_estimated"] is True

    def test_введённое_руками_не_перебивается(self):
        # Человек мог смотреть на пульсометр, а тот знает о нагрузке больше
        # формулы.
        user, _ = _person()
        WeightLog.objects.create(user=user, date=date.today(), weight_kg=Decimal("70"))

        r = _client(user).post(
            reverse("diary-workouts"),
            {"date": str(date.today()), "activity": self._activity().id, "duration_min": 60, "calories": 500},
            format="json",
        )

        assert r.data["calories"] == 500
        assert r.data["calories_estimated"] is False

    def test_без_веса_расход_пуст_а_не_выдуман(self):
        user, _ = _person()

        r = _client(user).post(
            reverse("diary-workouts"),
            {"date": str(date.today()), "activity": self._activity().id, "duration_min": 60},
            format="json",
        )

        assert r.status_code == 201, r.data
        assert r.data["calories"] is None

    def test_своё_название_без_справочника(self):
        user, _ = _person()

        r = _client(user).post(
            reverse("diary-workouts"),
            {"date": str(date.today()), "custom_name": "Сенокос", "duration_min": 90, "calories": 400},
            format="json",
        )

        assert r.status_code == 201, r.data
        assert r.data["title"] == "Сенокос"
        assert r.data["calories"] == 400

    def test_безымянное_занятие_не_принимается(self):
        # Пустая строка в списке читается как сбой загрузки.
        user, _ = _person()

        r = _client(user).post(
            reverse("diary-workouts"), {"date": str(date.today()), "duration_min": 30}, format="json"
        )

        assert r.status_code == 400

    def test_нелепая_длительность_не_принимается(self):
        user, _ = _person()

        r = _client(user).post(
            reverse("diary-workouts"),
            {"date": str(date.today()), "activity": self._activity().id, "duration_min": 5000},
            format="json",
        )

        assert r.status_code == 400

    def test_на_день_занятий_несколько(self):
        # Главное отличие от веса: пробежка утром и зал вечером — две записи,
        # а не перезапись одной.
        user, _ = _person()
        c = _client(user)
        today = str(date.today())
        c.post(
            reverse("diary-workouts"),
            {"date": today, "activity": self._activity().id, "duration_min": 40, "calories": 380},
            format="json",
        )
        c.post(
            reverse("diary-workouts"),
            {"date": today, "custom_name": "Зал", "duration_min": 60, "calories": 300},
            format="json",
        )

        rows = c.get(reverse("diary-workouts"), {"date": today}).data

        assert len(rows) == 2
        assert {r["title"] for r in rows} == {"Бег, 10 км/ч", "Зал"}

    def test_занятие_можно_убрать(self):
        user, _ = _person()
        c = _client(user)
        created = c.post(
            reverse("diary-workouts"),
            {"date": str(date.today()), "custom_name": "Ошибка", "duration_min": 30, "calories": 100},
            format="json",
        ).data

        r = c.delete(reverse("diary-workout-detail", args=[created["id"]]))

        assert r.status_code == 204
        assert WorkoutLog.objects.count() == 0

    def test_чужое_занятие_не_удалить(self):
        mine, _ = _person()
        other, other_member = _person("other@example.com", "Чужой")
        row = WorkoutLog.objects.create(
            user=other, member=other_member, date=date.today(), custom_name="Бег", duration_min=30
        )

        r = _client(mine).delete(reverse("diary-workout-detail", args=[row.id]))

        assert r.status_code == 403
        assert WorkoutLog.objects.filter(pk=row.pk).exists()

    def test_выдача_за_период(self):
        user, member = _person()
        WorkoutLog.objects.create(user=user, member=member, date=date.today(), custom_name="Сегодня", duration_min=30)
        WorkoutLog.objects.create(
            user=user,
            member=member,
            date=date.today() - timedelta(days=60),
            custom_name="Давно",
            duration_min=30,
        )

        rows = _client(user).get(reverse("diary-workouts"), {"days": "30"}).data

        assert [r["title"] for r in rows] == ["Сегодня"]


@pytest.mark.django_db
class TestРасходВСводкеДня:
    """Расход стоит в сводке отдельным числом — рядом с едой, но не в ней."""

    def _eat(self, member, day, calories):
        from apps.diary.models import DiaryEntry

        return DiaryEntry.objects.create(
            user=member.user,
            member=member,
            date=day,
            meal_type="lunch",
            custom_name="Обед",
            is_eaten=True,
            nutrition={"calories": calories, "proteins": 0, "fats": 0, "carbs": 0},
        )

    def test_калории_занятий_за_день_суммируются(self):
        user, member = _person()
        today = date.today()
        self._eat(member, today, 600)
        WorkoutLog.objects.create(
            user=user, member=member, date=today, custom_name="Бег", duration_min=30, calories=300
        )
        WorkoutLog.objects.create(
            user=user, member=member, date=today, custom_name="Зал", duration_min=60, calories=250
        )

        rows = _client(user).get(reverse("diary-stats"), {"from": str(today), "to": str(today)}).data

        assert rows[0]["burned"] == 550
        # Съеденное от тренировки не поехало: это разные числа и разные вопросы.
        assert rows[0]["actual"]["calories"] == 600

    def test_день_без_занятий_отдаёт_ноль_а_не_пусто(self):
        # «Не тренировался» — это ноль. Отдельное состояние «неизвестно»
        # экрану не нужно, а null в арифметике полос ломает подсчёт.
        user, member = _person()
        today = date.today()
        self._eat(member, today, 600)

        rows = _client(user).get(reverse("diary-stats"), {"from": str(today), "to": str(today)}).data

        assert rows[0]["burned"] == 0

    def test_день_с_занятием_и_без_еды_попадает_в_выдачу(self):
        # Иначе «Итоги» за такой день приехали бы пустыми, хотя занятие записано.
        user, member = _person()
        today = date.today()
        WorkoutLog.objects.create(
            user=user, member=member, date=today, custom_name="Бег", duration_min=30, calories=300
        )

        rows = _client(user).get(reverse("diary-stats"), {"from": str(today), "to": str(today)}).data

        assert len(rows) == 1
        assert rows[0]["burned"] == 300
        assert rows[0]["actual"]["calories"] == 0

    def test_занятие_без_калорий_в_сумму_не_входит(self):
        # Без веса расход не считается, и выдумывать его нельзя — такое занятие
        # в сводке просто не участвует.
        user, member = _person()
        today = date.today()
        WorkoutLog.objects.create(user=user, member=member, date=today, custom_name="Сенокос", duration_min=90)
        WorkoutLog.objects.create(
            user=user, member=member, date=today, custom_name="Бег", duration_min=30, calories=300
        )

        rows = _client(user).get(reverse("diary-stats"), {"from": str(today), "to": str(today)}).data

        assert rows[0]["burned"] == 300

    def test_чужое_занятие_в_свою_сводку_не_попадает(self):
        mine, my_member = _person()
        other, other_member = _person("other@example.com", "Чужой")
        today = date.today()
        WorkoutLog.objects.create(
            user=other, member=other_member, date=today, custom_name="Бег", duration_min=30, calories=300
        )
        self._eat(my_member, today, 600)

        rows = _client(mine).get(reverse("diary-stats"), {"from": str(today), "to": str(today)}).data

        assert rows[0]["burned"] == 0


@pytest.mark.django_db
class TestНормаНеМеняется:
    def test_цель_по_калориям_не_зависит_от_тренировок(self):
        """Ради этого правила всё и устроено именно так.

        Норма уже содержит коэффициент активности. Если бы тренировка её
        поднимала, человек на похудении получил бы разрешение съесть лишнее —
        и не узнал бы об этом.
        """
        user, _ = _person()
        user.profile.calorie_target = 2000
        user.profile.save(update_fields=["calorie_target"])
        WeightLog.objects.create(user=user, date=date.today(), weight_kg=Decimal("70"))

        _client(user).post(
            reverse("diary-workouts"),
            {
                "date": str(date.today()),
                "activity": ActivityType.objects.get(code="running_moderate").id,
                "duration_min": 60,
            },
            format="json",
        )

        user.profile.refresh_from_db()
        assert user.profile.calorie_target == 2000
