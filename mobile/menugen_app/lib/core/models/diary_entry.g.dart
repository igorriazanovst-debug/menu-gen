// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'diary_entry.dart';

DiaryEntry _\$DiaryEntryFromJson(Map<String, dynamic> json) => _DiaryEntry(
      id: json['id'] as int,
      date: json['date'] as String,
      mealType: json['meal_type'] as String,
      recipe: json['recipe'] as int?,
      recipeTitle: json['recipe_title'] as String?,
      customName: json['custom_name'] as String?,
      nutrition: json['nutrition'] as Map<String, dynamic>? ?? {},
      quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
    );

Map<String, dynamic> _\$DiaryEntryToJson(_DiaryEntry instance) => <String, dynamic>{
      'id': instance.id,
      'date': instance.date,
      'meal_type': instance.mealType,
      'recipe': instance.recipe,
      'recipe_title': instance.recipeTitle,
      'custom_name': instance.customName,
      'nutrition': instance.nutrition,
      'quantity': instance.quantity,
    };
