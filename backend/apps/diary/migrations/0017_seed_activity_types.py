"""MG_WORKOUT: посевной справочник физнагрузок.

Значения MET взяты из Compendium of Physical Activities — общепринятого
справочника, на который ссылаются и счётчики калорий, и научные работы.
Выдумывать свои числа нельзя: человек сверит с любым калькулятором и
перестанет верить всему остальному.

Набор намеренно небольшой и бытовой. Полный компендиум — это восемьсот
позиций вроде «игра на тубе стоя», и в списке выбора они утопили бы ходьбу и
бег. Чего нет в справочнике, человек впишет своим названием и своими
калориями.

Темпы у ходьбы и бега разведены отдельными строками, потому что разница
огромна: прогулочный шаг и быстрый различаются вдвое, а выбрать «ходьбу
вообще» значит ошибиться на эти же два раза.
"""

from django.db import migrations

# (код, название, группа, MET)
ACTIVITIES = [
    # Кардио
    ("walking_slow", "Ходьба прогулочная, 3 км/ч", "cardio", "2.8"),
    ("walking_moderate", "Ходьба обычная, 5 км/ч", "cardio", "3.5"),
    ("walking_brisk", "Ходьба быстрая, 6,5 км/ч", "cardio", "5.0"),
    ("walking_uphill", "Ходьба в гору", "cardio", "6.3"),
    ("nordic_walking", "Скандинавская ходьба", "cardio", "4.8"),
    ("running_slow", "Бег трусцой, 8 км/ч", "cardio", "8.3"),
    ("running_moderate", "Бег, 10 км/ч", "cardio", "9.8"),
    ("running_fast", "Бег быстрый, 12 км/ч", "cardio", "11.8"),
    ("cycling_light", "Велосипед прогулочный, до 16 км/ч", "cardio", "4.0"),
    ("cycling_moderate", "Велосипед, 16–20 км/ч", "cardio", "6.8"),
    ("cycling_fast", "Велосипед быстрый, от 20 км/ч", "cardio", "10.0"),
    ("swimming_light", "Плавание спокойное", "cardio", "5.8"),
    ("swimming_moderate", "Плавание в темпе", "cardio", "8.3"),
    ("elliptical", "Эллиптический тренажёр", "cardio", "5.0"),
    ("rowing_machine", "Гребной тренажёр", "cardio", "7.0"),
    ("jump_rope", "Скакалка", "cardio", "11.0"),
    ("stairs", "Подъём по лестнице", "cardio", "8.8"),
    ("skiing", "Лыжи", "cardio", "7.0"),
    ("skating", "Коньки", "cardio", "7.0"),
    ("aerobics", "Аэробика", "cardio", "6.5"),
    ("dancing", "Танцы", "cardio", "5.0"),
    # Силовые
    ("strength_light", "Силовая, спокойный темп", "strength", "3.5"),
    ("strength_moderate", "Силовая, обычный темп", "strength", "5.0"),
    ("strength_hard", "Силовая, тяжёлая", "strength", "6.0"),
    ("bodyweight", "Упражнения с весом тела", "strength", "4.3"),
    ("crossfit", "Круговая, кроссфит", "strength", "8.0"),
    ("hiit", "Интервальная высокой интенсивности", "strength", "8.0"),
    ("core", "Пресс и корпус", "strength", "3.8"),
    # Игры и спорт
    ("football", "Футбол", "sport", "7.0"),
    ("basketball", "Баскетбол", "sport", "6.5"),
    ("volleyball", "Волейбол", "sport", "4.0"),
    ("tennis", "Теннис", "sport", "7.3"),
    ("table_tennis", "Настольный теннис", "sport", "4.0"),
    ("badminton", "Бадминтон", "sport", "5.5"),
    ("boxing_bag", "Бокс, работа на мешке", "sport", "5.5"),
    ("martial_arts", "Единоборства", "sport", "10.3"),
    ("climbing", "Скалолазание", "sport", "8.0"),
    ("hiking", "Поход с рюкзаком", "sport", "7.3"),
    # Повседневное
    ("housework", "Уборка по дому", "daily", "3.3"),
    ("cooking", "Готовка", "daily", "2.5"),
    ("gardening", "Работа в саду", "daily", "3.8"),
    ("shoveling_snow", "Уборка снега", "daily", "5.3"),
    ("playing_with_kids", "Подвижные игры с детьми", "daily", "4.0"),
    ("shopping_walk", "Прогулка по магазинам", "daily", "2.3"),
    ("dog_walking", "Выгул собаки", "daily", "3.0"),
    # Растяжка и дыхание
    ("stretching", "Растяжка", "mind", "2.3"),
    ("yoga", "Йога", "mind", "3.0"),
    ("yoga_power", "Йога силовая", "mind", "4.0"),
    ("pilates", "Пилатес", "mind", "3.0"),
    ("breathing", "Дыхательная практика", "mind", "1.8"),
]


def seed(apps, schema_editor):
    ActivityType = apps.get_model("diary", "ActivityType")
    for order, (code, name, group, met) in enumerate(ACTIVITIES):
        # get_or_create, а не create: миграция обязана переживать повторный
        # прогон и уже заведённые руками записи с тем же кодом.
        ActivityType.objects.get_or_create(
            code=code,
            defaults={"name": name, "group": group, "met": met, "sort_order": order},
        )


def unseed(apps, schema_editor):
    ActivityType = apps.get_model("diary", "ActivityType")
    # Удаляем только посевные коды: заведённое руками не наше.
    ActivityType.objects.filter(code__in=[a[0] for a in ACTIVITIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("diary", "0016_activitytype_workoutlog_and_more")]
    operations = [migrations.RunPython(seed, unseed)]
