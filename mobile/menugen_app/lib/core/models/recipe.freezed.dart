// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'recipe.dart';

mixin _\$Recipe {
  int get id => throw _privateConstructorUsedError;
  String get title => throw _privateConstructorUsedError;
  String? get cookTime => throw _privateConstructorUsedError;
  int? get servings => throw _privateConstructorUsedError;
  List<Map<String, dynamic>> get ingredients => throw _privateConstructorUsedError;
  List<Map<String, dynamic>> get steps => throw _privateConstructorUsedError;
  Map<String, dynamic> get nutrition => throw _privateConstructorUsedError;
  List<String> get categories => throw _privateConstructorUsedError;
  String? get imageUrl => throw _privateConstructorUsedError;
  String? get videoUrl => throw _privateConstructorUsedError;
  String? get country => throw _privateConstructorUsedError;
  bool get isCustom => throw _privateConstructorUsedError;
  String? get authorName => throw _privateConstructorUsedError;
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
}

class _Recipe implements Recipe {
  const _Recipe({required this.id, required this.title, this.cookTime, this.servings,
      this.ingredients = const [], this.steps = const [], this.nutrition = const {},
      this.categories = const [], this.imageUrl, this.videoUrl,
      this.country, this.isCustom = false, this.authorName});
  @override final int id;
  @override final String title;
  @override final String? cookTime;
  @override final int? servings;
  @override final List<Map<String, dynamic>> ingredients;
  @override final List<Map<String, dynamic>> steps;
  @override final Map<String, dynamic> nutrition;
  @override final List<String> categories;
  @override final String? imageUrl;
  @override final String? videoUrl;
  @override final String? country;
  @override final bool isCustom;
  @override final String? authorName;
  @override
  Map<String, dynamic> toJson() => _\$RecipeToJson(this);
}
