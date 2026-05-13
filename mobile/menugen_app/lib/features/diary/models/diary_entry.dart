import 'package:equatable/equatable.dart';

/// Mirror of backend `DiaryEntry.MealType`.
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
  final int? recipeId;
  final String? recipeTitle;
  final String customName;
  final Map<String, dynamic> nutrition;
  final double quantity;
  final int? plannedMenuItemId; // null = manual entry (фактическое)
  final bool isEaten;           // MG-605.B

  const DiaryEntry({
    required this.id,
    required this.date,
    required this.mealType,
    required this.recipeId,
    required this.recipeTitle,
    required this.customName,
    required this.nutrition,
    required this.quantity,
    required this.plannedMenuItemId,
    required this.isEaten,
  });

  /// True if this entry was planned (came from menu import).
  bool get isPlanned => plannedMenuItemId != null;

  /// Display title — recipe title, custom name, or empty string.
  String get displayTitle =>
      (recipeTitle?.isNotEmpty == true) ? recipeTitle! : customName;

  factory DiaryEntry.fromJson(Map<String, dynamic> j) {
    final mt = MealType.tryParse(j['meal_type'] as String?) ?? MealType.snack;
    final qRaw = j['quantity'];
    final q = qRaw is num
        ? qRaw.toDouble()
        : (qRaw is String ? double.tryParse(qRaw) ?? 1.0 : 1.0);
    return DiaryEntry(
      id: (j['id'] as num).toInt(),
      date: j['date'] as String? ?? '',
      mealType: mt,
      recipeId: (j['recipe'] as num?)?.toInt(),
      recipeTitle: j['recipe_title'] as String?,
      customName: (j['custom_name'] as String?) ?? '',
      nutrition: (j['nutrition'] is Map)
          ? Map<String, dynamic>.from(j['nutrition'] as Map)
          : <String, dynamic>{},
      quantity: q,
      plannedMenuItemId: (j['planned_menu_item'] as num?)?.toInt(),
      isEaten: (j['is_eaten'] as bool?) ?? false,
    );
  }

  @override
  List<Object?> get props => [
        id,
        date,
        mealType,
        recipeId,
        recipeTitle,
        customName,
        nutrition,
        quantity,
        plannedMenuItemId,
        isEaten,
      ];
}
