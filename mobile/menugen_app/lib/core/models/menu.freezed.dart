// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'menu.dart';

mixin _\$Menu {
  int get id => throw _privateConstructorUsedError;
  String get startDate => throw _privateConstructorUsedError;
  String get endDate => throw _privateConstructorUsedError;
  int get periodDays => throw _privateConstructorUsedError;
  String get status => throw _privateConstructorUsedError;
  String get generatedAt => throw _privateConstructorUsedError;
  List<MenuItem> get items => throw _privateConstructorUsedError;
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
}

class _Menu implements Menu {
  const _Menu({required this.id, required this.startDate, required this.endDate,
      required this.periodDays, required this.status, required this.generatedAt,
      this.items = const []});
  @override final int id;
  @override final String startDate;
  @override final String endDate;
  @override final int periodDays;
  @override final String status;
  @override final String generatedAt;
  @override final List<MenuItem> items;
  @override
  Map<String, dynamic> toJson() => _\$MenuToJson(this);
}

mixin _\$MenuItem {
  int get id => throw _privateConstructorUsedError;
  int get dayOffset => throw _privateConstructorUsedError;
  String get mealType => throw _privateConstructorUsedError;
  Recipe get recipe => throw _privateConstructorUsedError;
  String? get memberName => throw _privateConstructorUsedError;
  double get quantity => throw _privateConstructorUsedError;
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
}

class _MenuItem implements MenuItem {
  const _MenuItem({required this.id, required this.dayOffset, required this.mealType,
      required this.recipe, this.memberName, this.quantity = 1.0});
  @override final int id;
  @override final int dayOffset;
  @override final String mealType;
  @override final Recipe recipe;
  @override final String? memberName;
  @override final double quantity;
  @override
  Map<String, dynamic> toJson() => _\$MenuItemToJson(this);
}
