class DiaryEntry {
  final int id;
  final String date;
  final String mealType;
  final int? recipe;
  final String? recipeTitle;
  final String? customName;
  final Map<String, dynamic> nutrition;
  final double quantity;

  const DiaryEntry({
    required this.id, required this.date, required this.mealType,
    this.recipe, this.recipeTitle, this.customName,
    this.nutrition = const {}, this.quantity = 1.0,
  });

  factory DiaryEntry.fromJson(Map<String, dynamic> json) => DiaryEntry(
        id: json['id'] as int? ?? 0,
        date: json['date'] as String? ?? '',
        mealType: json['meal_type'] as String? ?? '',
        recipe: json['recipe'] as int?,
        recipeTitle: json['recipe_title'] as String?,
        customName: json['custom_name'] as String?,
        nutrition: json['nutrition'] != null
            ? Map<String, dynamic>.from(json['nutrition'] as Map) : {},
        quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
      );

  Map<String, dynamic> toJson() => {
        'id': id, 'date': date, 'meal_type': mealType,
        if (recipe != null) 'recipe': recipe,
        if (recipeTitle != null) 'recipe_title': recipeTitle,
        if (customName != null) 'custom_name': customName,
        'nutrition': nutrition, 'quantity': quantity,
      };
}