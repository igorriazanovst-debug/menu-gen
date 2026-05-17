import 'package:equatable/equatable.dart';

/// Aggregated filter state for the Recipes screen.
/// All fields default to "no filter". Combine any subset.
class RecipeFilters extends Equatable {
  /// breakfast / lunch / dinner / snack — uses backend ?meal_type=.
  final String? mealType;

  /// «Суп» / «Салат» / «Выпечка» / «Десерт» / «Напиток» — uses ?dish_type=.
  final String? dishType;

  /// food_group: grain / protein / vegetable / fruit / dairy / oil / other.
  final String? foodGroup;

  /// Country (icontains).
  final String? country;

  /// Set of ingredient names entered by the user manually.
  final List<String> manualIngredients;

  /// AND/OR mode for [manualIngredients] (uses ingredients_all vs ingredients_any).
  final bool manualIngredientsAll;

  /// If true, send ?fridge_ingredients=<csv of fridge item names>
  /// (server ranks by match count).
  final bool useFridge;

  /// favorite=true/false; null = no filter.
  final bool? favorite;

  /// If true, send ?exclude_allergens=true.
  final bool excludeAllergens;

  const RecipeFilters({
    this.mealType,
    this.dishType,
    this.foodGroup,
    this.country,
    this.manualIngredients = const [],
    this.manualIngredientsAll = true,
    this.useFridge = false,
    this.favorite,
    this.excludeAllergens = false,
  });

  bool get isEmpty =>
      mealType == null &&
      dishType == null &&
      foodGroup == null &&
      (country == null || country!.isEmpty) &&
      manualIngredients.isEmpty &&
      !useFridge &&
      favorite == null &&
      !excludeAllergens;

  int get activeCount {
    var n = 0;
    if (mealType != null) n++;
    if (dishType != null) n++;
    if (foodGroup != null) n++;
    if (country != null && country!.isNotEmpty) n++;
    if (manualIngredients.isNotEmpty) n++;
    if (useFridge) n++;
    if (favorite != null) n++;
    if (excludeAllergens) n++;
    return n;
  }

  RecipeFilters copyWith({
    Object? mealType = _sentinel,
    Object? dishType = _sentinel,
    Object? foodGroup = _sentinel,
    Object? country = _sentinel,
    List<String>? manualIngredients,
    bool? manualIngredientsAll,
    bool? useFridge,
    Object? favorite = _sentinel,
    bool? excludeAllergens,
  }) {
    return RecipeFilters(
      mealType: identical(mealType, _sentinel) ? this.mealType : mealType as String?,
      dishType: identical(dishType, _sentinel) ? this.dishType : dishType as String?,
      foodGroup: identical(foodGroup, _sentinel) ? this.foodGroup : foodGroup as String?,
      country: identical(country, _sentinel) ? this.country : country as String?,
      manualIngredients: manualIngredients ?? this.manualIngredients,
      manualIngredientsAll: manualIngredientsAll ?? this.manualIngredientsAll,
      useFridge: useFridge ?? this.useFridge,
      favorite: identical(favorite, _sentinel) ? this.favorite : favorite as bool?,
      excludeAllergens: excludeAllergens ?? this.excludeAllergens,
    );
  }

  /// Convert filters to the query params for the backend /recipes/ list.
  /// [fridgeNames] is the list of fridge item names; required if [useFridge].
  Map<String, dynamic> toQueryParams({
    String? search,
    int page = 1,
    List<String>? fridgeNames,
  }) {
    final p = <String, dynamic>{'page': page};
    if (search != null && search.isNotEmpty) p['search'] = search;
    if (mealType != null) p['meal_type'] = mealType;
    if (dishType != null) p['dish_type'] = dishType;
    if (foodGroup != null) p['food_group'] = foodGroup;
    if (country != null && country!.isNotEmpty) p['country'] = country;
    if (manualIngredients.isNotEmpty) {
      final csv = manualIngredients.join(',');
      p[manualIngredientsAll ? 'ingredients_all' : 'ingredients_any'] = csv;
    }
    if (useFridge && fridgeNames != null && fridgeNames.isNotEmpty) {
      p['fridge_ingredients'] = fridgeNames.join(',');
    }
    if (favorite != null) p['favorite'] = favorite! ? 'true' : 'false';
    if (excludeAllergens) p['exclude_allergens'] = 'true';
    return p;
  }

  @override
  List<Object?> get props => [
        mealType,
        dishType,
        foodGroup,
        country,
        manualIngredients,
        manualIngredientsAll,
        useFridge,
        favorite,
        excludeAllergens,
      ];

  static const _sentinel = Object();
}
