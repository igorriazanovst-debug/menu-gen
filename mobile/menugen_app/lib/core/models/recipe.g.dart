// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'recipe.dart';

Recipe _$RecipeFromJson(Map<String, dynamic> json) => _Recipe(
      id: json['id'] as int,
      title: json['title'] as String,
      cookTime: json['cook_time'] as String?,
      servings: json['servings'] as int?,
      ingredients: (json['ingredients'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>).toList() ?? [],
      steps: (json['steps'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>).toList() ?? [],
      nutrition: json['nutrition'] as Map<String, dynamic>? ?? {},
      categories: (json['categories'] as List<dynamic>?)
              ?.map((e) => e as String).toList() ?? [],
      imageUrl: json['image_url'] as String?,
      videoUrl: json['video_url'] as String?,
      country: json['country'] as String?,
      isCustom: json['is_custom'] as bool? ?? false,
      authorName: json['author_name'] as String?,
    );

Map<String, dynamic> _$RecipeToJson(_Recipe instance) => <String, dynamic>{
      'id': instance.id,
      'title': instance.title,
      'cook_time': instance.cookTime,
      'servings': instance.servings,
      'ingredients': instance.ingredients,
      'steps': instance.steps,
      'nutrition': instance.nutrition,
      'categories': instance.categories,
      'image_url': instance.imageUrl,
      'video_url': instance.videoUrl,
      'country': instance.country,
      'is_custom': instance.isCustom,
      'author_name': instance.authorName,
    };
