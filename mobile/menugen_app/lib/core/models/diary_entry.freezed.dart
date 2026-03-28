// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'diary_entry.dart';

mixin _\$DiaryEntry {
  int get id => throw _privateConstructorUsedError;
  String get date => throw _privateConstructorUsedError;
  String get mealType => throw _privateConstructorUsedError;
  int? get recipe => throw _privateConstructorUsedError;
  String? get recipeTitle => throw _privateConstructorUsedError;
  String? get customName => throw _privateConstructorUsedError;
  Map<String, dynamic> get nutrition => throw _privateConstructorUsedError;
  double get quantity => throw _privateConstructorUsedError;
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
}

class _DiaryEntry implements DiaryEntry {
  const _DiaryEntry({required this.id, required this.date, required this.mealType,
      this.recipe, this.recipeTitle, this.customName,
      this.nutrition = const {}, this.quantity = 1.0});
  @override final int id;
  @override final String date;
  @override final String mealType;
  @override final int? recipe;
  @override final String? recipeTitle;
  @override final String? customName;
  @override final Map<String, dynamic> nutrition;
  @override final double quantity;
  @override
  Map<String, dynamic> toJson() => _\$DiaryEntryToJson(this);
}
