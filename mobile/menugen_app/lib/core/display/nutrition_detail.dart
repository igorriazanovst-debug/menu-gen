// MG_NUTRIDETAIL: сколько чисел показывать в строке еды.
//
// Настройка отображения, а не данных: числа у записи те же, меняется только
// то, что из них видно. Живёт в аккаунте (Profile.nutrition_detail), поэтому
// одна и та же в приложении и в вебе — иначе один и тот же дневник выглядел
// бы на телефоне и в браузере по-разному, и настройка превратилась бы в две.
//
// Умолчание — «обычно»: дневник заводят ради состава еды, и прятать БЖУ по
// умолчанию значит прятать ответ на главный вопрос.

enum NutritionDetail { short, normal, detailed }

extension NutritionDetailX on NutritionDetail {
  /// Код для API и локального хранения (совпадает с Profile.NutritionDetail).
  String get code {
    switch (this) {
      case NutritionDetail.short:
        return 'short';
      case NutritionDetail.detailed:
        return 'detailed';
      case NutritionDetail.normal:
        return 'normal';
    }
  }

  String get label {
    switch (this) {
      case NutritionDetail.short:
        return 'Кратко';
      case NutritionDetail.detailed:
        return 'Подробно';
      case NutritionDetail.normal:
        return 'Обычно';
    }
  }

  /// Что человек увидит, выбрав это. Подпись нужна рядом с названием: «кратко»
  /// и «подробно» сами по себе не говорят, чего именно станет меньше.
  String get hint {
    switch (this) {
      case NutritionDetail.short:
        return 'Только калории';
      case NutritionDetail.detailed:
        return 'Калории, БЖУ и вес порции';
      case NutritionDetail.normal:
        return 'Калории и БЖУ';
    }
  }

  bool get showMacros => this != NutritionDetail.short;
  bool get showGrams => this == NutritionDetail.detailed;
}

NutritionDetail nutritionDetailFromCode(String? code) {
  switch (code) {
    case 'short':
      return NutritionDetail.short;
    case 'detailed':
      return NutritionDetail.detailed;
    default:
      // Незнакомое значение — умолчание, а не исключение: сервер старше
      // приложения (или новее) не повод показывать пустой экран.
      return NutritionDetail.normal;
  }
}

/// «Б 12 · Ж 8 · У 30 г» — буквами, а не словами.
///
/// В заголовке приёма стоят полные слова («Белки 12 г · Жиры 8 г …»), и это
/// правильно: там место есть, и там же расшифровка букв. В строке записи
/// полные слова не помещаются рядом с названием блюда и обрезаются
/// многоточием — то есть пропадает то самое, ради чего их и показывают.
///
/// Пусто — когда чисел нет вовсе: «Б 0 · Ж 0 · У 0 г» это не данные, а шум.
String macrosShort({required double proteins, required double fats, required double carbs}) {
  if (proteins <= 0 && fats <= 0 && carbs <= 0) return '';
  String n(double v) {
    if (v <= 0) return '0';
    // Доли грамма показываем только у мелких значений: «Б 12,3» в строке — вид
    // точности, которой у таблиц КБЖУ нет, а «У 0,7» — настоящее число.
    return v >= 10 ? v.round().toString() : v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1);
  }

  return 'Б ${n(proteins)} · Ж ${n(fats)} · У ${n(carbs)} г';
}
