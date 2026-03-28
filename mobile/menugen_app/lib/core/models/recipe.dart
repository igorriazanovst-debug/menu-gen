class Recipe {
  final int id;
  final String title;
  final String? cookTime;
  final int? servings;
  final List<Map<String, dynamic>> ingredients;
  final List<Map<String, dynamic>> steps;
  final Map<String, dynamic> nutrition;
  final List<String> categories;
  final String? imageUrl;
  final String? videoUrl;
  final String? country;
  final bool isCustom;
  final String? authorName;

  const Recipe({
    required this.id,
    required this.title,
    this.cookTime,
    this.servings,
    this.ingredients = const [],
    this.steps = const [],
    this.nutrition = const {},
    this.categories = const [],
    this.imageUrl,
    this.videoUrl,
    this.country,
    this.isCustom = false,
    this.authorName,
  });

  factory Recipe.fromJson(Map<String, dynamic> json) => Recipe(
        id: json['id'] as int? ?? 0,
        title: json['title'] as String? ?? '',
        cookTime: json['cook_time'] as String?,
        servings: json['servings'] as int?,
        ingredients: (json['ingredients'] as List?)
                ?.map((e) => Map<String, dynamic>.from(e as Map))
                .toList() ?? [],
        steps: (json['steps'] as List?)
                ?.map((e) => Map<String, dynamic>.from(e as Map))
                .toList() ?? [],
        nutrition: json['nutrition'] != null
            ? Map<String, dynamic>.from(json['nutrition'] as Map) : {},
        categories: (json['categories'] as List?)
                ?.map((e) => e.toString()).toList() ?? [],
        imageUrl: json['image_url'] as String?,
        videoUrl: json['video_url'] as String?,
        country: json['country'] as String?,
        isCustom: json['is_custom'] as bool? ?? false,
        authorName: json['author_name'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id, 'title': title,
        if (cookTime != null) 'cook_time': cookTime,
        if (servings != null) 'servings': servings,
        'ingredients': ingredients, 'steps': steps,
        'nutrition': nutrition, 'categories': categories,
        if (imageUrl != null) 'image_url': imageUrl,
        if (videoUrl != null) 'video_url': videoUrl,
        if (country != null) 'country': country,
        'is_custom': isCustom,
        if (authorName != null) 'author_name': authorName,
      };
}