import 'package:equatable/equatable.dart';

/// One nutrition bucket — matches backend `_NutritionBucketSerializer`.
class NutritionBucket extends Equatable {
  final double calories;
  final double proteins;
  final double fats;
  final double carbs;

  const NutritionBucket({
    required this.calories,
    required this.proteins,
    required this.fats,
    required this.carbs,
  });

  const NutritionBucket.zero()
      : calories = 0,
        proteins = 0,
        fats = 0,
        carbs = 0;

  factory NutritionBucket.fromJson(Map<String, dynamic>? j) {
    if (j == null) return const NutritionBucket.zero();
    double v(dynamic x) =>
        x is num ? x.toDouble() : (x is String ? double.tryParse(x) ?? 0 : 0);
    return NutritionBucket(
      calories: v(j['calories']),
      proteins: v(j['proteins']),
      fats: v(j['fats']),
      carbs: v(j['carbs']),
    );
  }

  @override
  List<Object?> get props => [calories, proteins, fats, carbs];
}

/// Per-day stats from `GET /api/v1/diary/stats/?from=&to=`.
///
/// Backend (MG-605.D) returns a *plain array* (not paginated):
/// `[{date, planned, actual, total}]`.
class DiaryDayStats extends Equatable {
  final String date;
  final NutritionBucket planned;
  final NutritionBucket actual;
  final NutritionBucket total;

  const DiaryDayStats({
    required this.date,
    required this.planned,
    required this.actual,
    required this.total,
  });

  factory DiaryDayStats.fromJson(Map<String, dynamic> j) => DiaryDayStats(
        date: j['date'] as String? ?? '',
        planned: NutritionBucket.fromJson(j['planned'] as Map<String, dynamic>?),
        actual: NutritionBucket.fromJson(j['actual'] as Map<String, dynamic>?),
        total: NutritionBucket.fromJson(j['total'] as Map<String, dynamic>?),
      );

  @override
  List<Object?> get props => [date, planned, actual, total];
}
