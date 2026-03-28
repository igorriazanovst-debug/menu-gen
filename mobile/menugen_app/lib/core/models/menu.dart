import 'package:freezed_annotation/freezed_annotation.dart';
part 'menu.freezed.dart';
part 'menu.g.dart';

@freezed
class Menu with _$Menu {
  const factory Menu({
    required int id,
    required String startDate,
    required String endDate,
    required int periodDays,
    required String status,
    required String generatedAt,
    @Default([]) List<MenuItem> items,
  }) = _Menu;

  factory Menu.fromJson(Map<String, dynamic> json) => _$MenuFromJson(json);
}

@freezed
class MenuItem with _$MenuItem {
  const factory MenuItem({
    required int id,
    required int dayOffset,
    required String mealType,
    required Recipe recipe,
    String? memberName,
    @Default(1.0) double quantity,
  }) = _MenuItem;

  factory MenuItem.fromJson(Map<String, dynamic> json) => _$MenuItemFromJson(json);
}
