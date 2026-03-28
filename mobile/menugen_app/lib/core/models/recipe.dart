import 'package:freezed_annotation/freezed_annotation.dart';
part 'recipe.freezed.dart';
part 'recipe.g.dart';

@freezed
class Recipe with _$Recipe {
  const factory Recipe({
    required int id,
    required String title,
    String? cookTime,
    int? servings,
    @Default([]) List<Map<String, dynamic>> ingredients,
    @Default([]) List<Map<String, dynamic>> steps,
    @Default({}) Map<String, dynamic> nutrition,
    @Default([]) List<String> categories,
    String? imageUrl,
    String? videoUrl,
    String? country,
    @Default(false) bool isCustom,
    String? authorName,
  }) = _Recipe;

  factory Recipe.fromJson(Map<String, dynamic> json) => _$RecipeFromJson(json);
}
