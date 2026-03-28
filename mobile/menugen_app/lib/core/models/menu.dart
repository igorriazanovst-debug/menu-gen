import 'recipe.dart';

class Menu {
  final int id;
  final String startDate;
  final String endDate;
  final int periodDays;
  final String status;
  final String generatedAt;
  final List<MenuItem> items;

  const Menu({
    required this.id, required this.startDate, required this.endDate,
    required this.periodDays, required this.status, required this.generatedAt,
    this.items = const [],
  });

  factory Menu.fromJson(Map<String, dynamic> json) => Menu(
        id: json['id'] as int? ?? 0,
        startDate: json['start_date'] as String? ?? '',
        endDate: json['end_date'] as String? ?? '',
        periodDays: json['period_days'] as int? ?? 7,
        status: json['status'] as String? ?? '',
        generatedAt: json['generated_at'] as String? ?? '',
        items: (json['items'] as List?)
                ?.map((e) => MenuItem.fromJson(Map<String, dynamic>.from(e as Map)))
                .toList() ?? [],
      );

  Map<String, dynamic> toJson() => {
        'id': id, 'start_date': startDate, 'end_date': endDate,
        'period_days': periodDays, 'status': status, 'generated_at': generatedAt,
        'items': items.map((e) => e.toJson()).toList(),
      };
}

class MenuItem {
  final int id;
  final int dayOffset;
  final String mealType;
  final Recipe recipe;
  final String? memberName;
  final double quantity;

  const MenuItem({
    required this.id, required this.dayOffset, required this.mealType,
    required this.recipe, this.memberName, this.quantity = 1.0,
  });

  factory MenuItem.fromJson(Map<String, dynamic> json) => MenuItem(
        id: json['id'] as int? ?? 0,
        dayOffset: json['day_offset'] as int? ?? 0,
        mealType: json['meal_type'] as String? ?? '',
        recipe: Recipe.fromJson(Map<String, dynamic>.from(json['recipe'] as Map? ?? {})),
        memberName: json['member_name'] as String?,
        quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
      );

  Map<String, dynamic> toJson() => {
        'id': id, 'day_offset': dayOffset, 'meal_type': mealType,
        'recipe': recipe.toJson(),
        if (memberName != null) 'member_name': memberName,
        'quantity': quantity,
      };
}