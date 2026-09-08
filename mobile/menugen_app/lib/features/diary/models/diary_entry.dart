import 'package:equatable/equatable.dart';

/// Mirror of backend `DiaryEntry.MealType`.
/// MG_MEALSLOT: точное место приёма в дне.
///
/// [MealType] отвечает на вопрос «какого рода эта еда» — по нему сервер
/// подбирает рецепты, и перекус там один: для подбора первый и второй ничем не
/// отличаются. Человеку в дневнике нужно другое: при пяти приёмах перекуса два,
/// они в разное время и с разной едой, и в одной куче читаются плохо.
///
/// Порядок значений — по ходу дня: дневник читают сверху вниз, как день.
enum MealSlot {
  breakfast('breakfast', 'Завтрак', MealType.breakfast),
  snack1('snack1', 'Перекус 1', MealType.snack),
  lunch('lunch', 'Обед', MealType.lunch),
  snack2('snack2', 'Перекус 2', MealType.snack),
  dinner('dinner', 'Ужин', MealType.dinner);

  final String value;
  final String label;
  final MealType mealType;
  const MealSlot(this.value, this.label, this.mealType);

  static MealSlot? tryParse(String? raw) {
    if (raw == null) return null;
    for (final s in MealSlot.values) {
      if (s.value == raw) return s;
    }
    return null;
  }

  /// Слот по умолчанию для рода еды. Перекус попадает в первый: какой он был на
  /// самом деле, не знает никто — до появления слота это нигде не хранилось.
  static MealSlot fromMealType(MealType type) {
    switch (type) {
      case MealType.breakfast:
        return MealSlot.breakfast;
      case MealType.lunch:
        return MealSlot.lunch;
      case MealType.dinner:
        return MealSlot.dinner;
      case MealType.snack:
        return MealSlot.snack1;
    }
  }

  /// Раскладка дня: три приёма или пять.
  static List<MealSlot> forPlan(String? mealPlanType) =>
      mealPlanType == '5'
          ? MealSlot.values
          : const [MealSlot.breakfast, MealSlot.lunch, MealSlot.dinner];
}

enum MealType {
  breakfast('breakfast', 'Завтрак'),
  lunch('lunch', 'Обед'),
  dinner('dinner', 'Ужин'),
  snack('snack', 'Перекус');

  final String value;
  final String label;
  const MealType(this.value, this.label);

  static MealType? tryParse(String? raw) {
    if (raw == null) return null;
    for (final m in MealType.values) {
      if (m.value == raw) return m;
    }
    return null;
  }
}

/// One diary entry as returned by `GET /api/v1/diary/`.
///
/// Maps to `DiaryEntrySerializer` (read shape):
///   id, date, meal_type, recipe (FK id), recipe_title (derived),
///   custom_name, nutrition (dict), quantity (decimal),
///   planned_menu_item (FK id, MG-605.B), is_eaten (MG-605.B), created_at.
class DiaryEntry extends Equatable {
  final int id;
  final String date;            // YYYY-MM-DD
  final MealType mealType;
  final MealSlot mealSlot; // MG_MEALSLOT
  final int? recipeId;
  final String? recipeTitle;
  final String customName;
  final Map<String, dynamic> nutrition;
  final double quantity;
  /// MG_DIARYGRAMS: сколько съедено, граммов на одну порцию. null — вес
  /// неизвестен: так у старых записей и у порционных («1 порция супа»).
  final int? grams;
  final int? plannedMenuItemId; // null = manual entry (фактическое)
  final bool isEaten;           // MG-605.B
  final bool isPlannedFlag;     // DIARY_COPY_V3 (explicit plan flag)

  const DiaryEntry({
    required this.id,
    required this.date,
    required this.mealType,
    required this.mealSlot, // MG_MEALSLOT
    required this.recipeId,
    required this.recipeTitle,
    required this.customName,
    required this.nutrition,
    required this.quantity,
    this.grams, // MG_DIARYGRAMS
    required this.plannedMenuItemId,
    required this.isEaten,
    this.isPlannedFlag = false, // DIARY_COPY_V3
  });

  /// True if this entry was planned (came from menu import).
  bool get isPlanned => isPlannedFlag || plannedMenuItemId != null; // DIARY_COPY_V3

  /// Display title — recipe title, custom name, or empty string.
  String get displayTitle =>
      (recipeTitle?.isNotEmpty == true) ? recipeTitle! : customName;

  // MG_SKIN: lightweight copy for optimistic is_eaten flips.
  DiaryEntry copyWith({bool? isEaten}) => DiaryEntry(
        id: id,
        date: date,
        mealType: mealType,
        mealSlot: mealSlot,
        recipeId: recipeId,
        recipeTitle: recipeTitle,
        customName: customName,
        nutrition: nutrition,
        quantity: quantity,
        grams: grams,
        plannedMenuItemId: plannedMenuItemId,
        isEaten: isEaten ?? this.isEaten,
        isPlannedFlag: isPlannedFlag,
      );

  factory DiaryEntry.fromJson(Map<String, dynamic> j) {
    final mt = MealType.tryParse(j['meal_type'] as String?) ?? MealType.snack;
    // MG_MEALSLOT: слот приходит с сервера всегда. Запасной путь — на ответ из
    // офлайн-кэша, снятый до обновления приложения.
    final slot = MealSlot.tryParse(j['meal_slot'] as String?) ?? MealSlot.fromMealType(mt);
    final qRaw = j['quantity'];
    final q = qRaw is num
        ? qRaw.toDouble()
        : (qRaw is String ? double.tryParse(qRaw) ?? 1.0 : 1.0);
    return DiaryEntry(
      id: (j['id'] as num).toInt(),
      date: j['date'] as String? ?? '',
      mealType: mt,
      mealSlot: slot,
      recipeId: (j['recipe'] as num?)?.toInt(),
      recipeTitle: j['recipe_title'] as String?,
      customName: (j['custom_name'] as String?) ?? '',
      nutrition: (j['nutrition'] is Map)
          ? Map<String, dynamic>.from(j['nutrition'] as Map)
          : <String, dynamic>{},
      quantity: q,
      grams: (j['grams'] as num?)?.toInt(), // MG_DIARYGRAMS
      plannedMenuItemId: (j['planned_menu_item'] as num?)?.toInt(),
      isEaten: (j['is_eaten'] as bool?) ?? false,
      isPlannedFlag: (j['is_planned'] as bool?) ?? false, // DIARY_COPY_V3
    );
  }

  @override
  List<Object?> get props => [
        id,
        date,
        mealType,
        mealSlot,
        recipeId,
        recipeTitle,
        customName,
        nutrition,
        quantity,
        grams,
        plannedMenuItemId,
        isEaten,
      ];
}
