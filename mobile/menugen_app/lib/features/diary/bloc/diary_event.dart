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

/// MG_SKIN: toggle is_eaten on many entries at once (branch / whole plan).
class DiaryMarkManyEatenRequested extends DiaryEvent {
  final List<int> entryIds;
  final bool isEaten;
  const DiaryMarkManyEatenRequested(
      {required this.entryIds, required this.isEaten});
  @override
  List<Object?> get props => [entryIds, isEaten];
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

/// DIARY_EDIT: PATCH одной записи (название/приём/кол-во/КБЖУ).
class DiaryUpdateRequested extends DiaryEvent {
  final int entryId;
  final Map<String, dynamic> fields; // тело PATCH /diary/{id}/
  const DiaryUpdateRequested({required this.entryId, required this.fields});
  @override
  List<Object?> get props => [entryId, fields];
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

// DIARY_V2: water tracker events.
class DiaryWaterSetRequested extends DiaryEvent {
  final String date;
  final int waterMl;
  final int? memberId;
  const DiaryWaterSetRequested({required this.date, required this.waterMl, this.memberId});
  @override
  List<Object?> get props => [date, waterMl, memberId];
}

// DIARY_COPY_V3: copy selected entries into a target day as plan.
class DiaryCopyRequested extends DiaryEvent {
  final List<int> entryIds;
  final String targetDate; // YYYY-MM-DD
  final int? memberId;
  const DiaryCopyRequested({
    required this.entryIds,
    required this.targetDate,
    this.memberId,
  });
  @override
  List<Object?> get props => [entryIds, targetDate, memberId];
}
