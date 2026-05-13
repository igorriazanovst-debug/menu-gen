part of 'diary_bloc.dart';

abstract class DiaryEvent extends Equatable {
  const DiaryEvent();
  @override
  List<Object?> get props => [];
}

/// Load entries + stats for one day (optionally for a specific family member).
class DiaryLoadRequested extends DiaryEvent {
  final String date;     // YYYY-MM-DD
  final int? memberId;   // null = self
  const DiaryLoadRequested({required this.date, this.memberId});

  /// Convenience positional form, kept for backwards-compatible tests.
  factory DiaryLoadRequested.forDate(String date) =>
      DiaryLoadRequested(date: date);

  @override
  List<Object?> get props => [date, memberId];
}

/// Toggle is_eaten on a planned entry.
class DiaryMarkEatenRequested extends DiaryEvent {
  final int entryId;
  final bool isEaten;
  const DiaryMarkEatenRequested({required this.entryId, required this.isEaten});
  @override
  List<Object?> get props => [entryId, isEaten];
}

/// Add a manual (factual) entry — no plan, immediate fact.
class DiaryAddManualRequested extends DiaryEvent {
  final String date;
  final MealType mealType;
  final int? recipeId;
  final String customName;
  final double quantity;
  final Map<String, dynamic> nutrition;
  const DiaryAddManualRequested({
    required this.date,
    required this.mealType,
    this.recipeId,
    this.customName = '',
    this.quantity = 1.0,
    this.nutrition = const {},
  });
  @override
  List<Object?> get props =>
      [date, mealType, recipeId, customName, quantity, nutrition];
}

class DiaryDeleteRequested extends DiaryEvent {
  final int entryId;
  const DiaryDeleteRequested(this.entryId);
  @override
  List<Object?> get props => [entryId];
}

/// MG-605.D — import all MenuItems of a menu into the diary for a given day.
class DiaryImportFromMenuRequested extends DiaryEvent {
  final int menuId;
  final String date;
  final int? memberId;
  const DiaryImportFromMenuRequested({
    required this.menuId,
    required this.date,
    this.memberId,
  });
  @override
  List<Object?> get props => [menuId, date, memberId];
}
