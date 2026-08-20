"""MG_TRAINER: неделя клиента одним ответом.

Специалисту нужен не список записей дневника, а ответ на вопрос «ест ли клиент
то, о чём договорились». Раньше это можно было выяснить, только листая дни по
одному.

Считаем по существующим таблицам, ничего нового не храня: `DiaryEntry` знает,
что съедено и было ли это запланировано, `WaterLog` — воду, `Profile` — цели.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def member_summary(member, days: int = 7, today=None) -> dict:
    """Сводка по участнику за последние `days` дней, включая сегодня."""
    from apps.diary.models import DiaryEntry, WaterLog

    today = today or timezone.localdate()
    start = today - timedelta(days=days - 1)

    entries = list(DiaryEntry.objects.filter(member=member, date__gte=start, date__lte=today))
    eaten = [e for e in entries if e.is_eaten]

    # Дни считаем по фактам, а не по числу записей: три приёма в один день —
    # это один день соблюдения, а не три.
    days_with_food = {e.date for e in eaten}
    # «По плану» — съедено то, что было запланировано (из меню или руками).
    days_on_plan = {e.date for e in eaten if e.is_planned or e.planned_menu_item_id}

    # Считаем тем же кодом, что и дневник: свой разбор nutrition разошёлся бы
    # с ним на первой же записи со значением-словарём.
    from apps.diary.entry_nutrition import add_bucket, empty_bucket, entry_nutrition

    totals = empty_bucket()
    for e in eaten:
        add_bucket(totals, entry_nutrition(e))

    water_rows = WaterLog.objects.filter(member=member, date__gte=start, date__lte=today)
    water_total = sum(w.water_ml for w in water_rows)
    water_days = sum(1 for w in water_rows if w.water_ml > 0)

    # Среднее — по дням, когда человек вообще что-то записал. Делить на 7, когда
    # записей три, значит показать тренеру втрое заниженный калораж и увести
    # разговор не туда.
    tracked = len(days_with_food) or 1

    profile = getattr(getattr(member, "user", None), "profile", None)
    targets = {
        "calories": getattr(profile, "calorie_target", None),
        "proteins": _decimal_to_float(getattr(profile, "protein_target_g", None)),
        "fats": _decimal_to_float(getattr(profile, "fat_target_g", None)),
        "carbs": _decimal_to_float(getattr(profile, "carb_target_g", None)),
    }

    return {
        "member_id": member.id,
        "member_name": getattr(getattr(member, "user", None), "name", "") or "",
        "days": days,
        "days_tracked": len(days_with_food),
        "days_on_plan": len(days_on_plan),
        "entries_total": len(entries),
        "entries_eaten": len(eaten),
        "avg_per_tracked_day": {
            "calories": round(totals["calories"] / tracked),
            "proteins": round(totals["proteins"] / tracked, 1),
            "fats": round(totals["fats"] / tracked, 1),
            "carbs": round(totals["carbs"] / tracked, 1),
        },
        "targets": targets,
        "water": {"total_ml": water_total, "days_logged": water_days},
        "weight": _weight_block(member, start, today),
    }


def _decimal_to_float(value):
    return float(value) if value is not None else None


def _weight_block(member, start, today) -> dict:
    """Вес: первая и последняя точки за период плюс общая динамика."""
    from apps.diary.models import WeightLog

    period = list(WeightLog.objects.filter(member=member, date__gte=start, date__lte=today).order_by("date"))
    latest = WeightLog.objects.filter(member=member).order_by("-date").first()
    if not period:
        return {
            "first": None,
            "last": float(latest.weight_kg) if latest else None,
            "last_date": str(latest.date) if latest else None,
            "change_kg": None,
            "points": 0,
        }
    first_kg = float(period[0].weight_kg)
    last_kg = float(period[-1].weight_kg)
    return {
        "first": first_kg,
        "last": last_kg,
        "last_date": str(period[-1].date),
        "change_kg": round(last_kg - first_kg, 1),
        "points": len(period),
    }


def family_summary(family, days: int = 7, today=None) -> list[dict]:
    """Сводка по всем участникам семьи."""
    from apps.family.models import FamilyMember

    members = FamilyMember.objects.filter(family=family).select_related("user", "user__profile")
    return [member_summary(m, days=days, today=today) for m in members]
