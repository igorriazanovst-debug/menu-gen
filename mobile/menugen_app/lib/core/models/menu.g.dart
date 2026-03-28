// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'menu.dart';

Menu _\$MenuFromJson(Map<String, dynamic> json) => _Menu(
      id: json['id'] as int,
      startDate: json['start_date'] as String,
      endDate: json['end_date'] as String,
      periodDays: json['period_days'] as int,
      status: json['status'] as String? ?? 'active',
      generatedAt: json['generated_at'] as String,
      items: (json['items'] as List<dynamic>?)
              ?.map((e) => MenuItem.fromJson(e as Map<String, dynamic>)).toList() ?? [],
    );

Map<String, dynamic> _\$MenuToJson(_Menu instance) => <String, dynamic>{
      'id': instance.id,
      'start_date': instance.startDate,
      'end_date': instance.endDate,
      'period_days': instance.periodDays,
      'status': instance.status,
      'generated_at': instance.generatedAt,
      'items': instance.items.map((e) => e.toJson()).toList(),
    };

MenuItem _\$MenuItemFromJson(Map<String, dynamic> json) => _MenuItem(
      id: json['id'] as int,
      dayOffset: json['day_offset'] as int,
      mealType: json['meal_type'] as String,
      recipe: Recipe.fromJson(json['recipe'] as Map<String, dynamic>),
      memberName: json['member_name'] as String?,
      quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
    );

Map<String, dynamic> _\$MenuItemToJson(_MenuItem instance) => <String, dynamic>{
      'id': instance.id,
      'day_offset': instance.dayOffset,
      'meal_type': instance.mealType,
      'recipe': instance.recipe.toJson(),
      'member_name': instance.memberName,
      'quantity': instance.quantity,
    };
