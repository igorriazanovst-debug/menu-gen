// MG_WORKOUT: занятие в дневнике и справочник занятий.
//
// Расход в дневную норму не вычитается и вычитаться не должен: норма уже
// содержит коэффициент активности, и прибавка за каждую тренировку посчитала
// бы его дважды. В «Итогах» расход стоит отдельным числом — см. серверный
// apps/diary/workout_calories.py, где это правило записано целиком.
import 'package:equatable/equatable.dart';

/// Запись справочника: `GET /api/v1/diary/activities/`.
class ActivityType extends Equatable {
  final int id;
  final String name;

  /// Группа (`cardio`, `strength`, `sport`, `daily`, `mind`) и её название
  /// по-русски: заголовки в списке выбора приходят с сервера, а не собираются
  /// здесь из кода группы.
  final String group;
  final String groupLabel;

  const ActivityType({
    required this.id,
    required this.name,
    required this.group,
    required this.groupLabel,
  });

  factory ActivityType.fromJson(Map<String, dynamic> j) => ActivityType(
        id: (j['id'] as num).toInt(),
        name: (j['name'] as String?) ?? '',
        group: (j['group'] as String?) ?? '',
        groupLabel: (j['group_label'] as String?) ?? '',
      );

  @override
  List<Object?> get props => [id, name, group, groupLabel];
}

/// Одно занятие: `GET/POST /api/v1/diary/workouts/`.
class WorkoutLog extends Equatable {
  final int id;
  final String date;
  final String title;
  final int durationMin;

  /// Потрачено, ккал. null — считать было не из чего: без веса расход не
  /// считается, и выдумывать его нельзя (пустое честнее неверного числа).
  final int? calories;

  /// Посчитали мы или вписал человек. Нужно, чтобы не выдавать свою оценку
  /// за показание пульсометра.
  final bool caloriesEstimated;

  /// MG_HEADKEEPS: имя того, кто записал занятие, если это не сам владелец, —
  /// глава семьи или тренер. Пусто — записал сам.
  final String? addedByName;

  const WorkoutLog({
    required this.id,
    required this.date,
    required this.title,
    required this.durationMin,
    required this.calories,
    required this.caloriesEstimated,
    this.addedByName,
  });

  factory WorkoutLog.fromJson(Map<String, dynamic> j) => WorkoutLog(
        id: (j['id'] as num).toInt(),
        date: (j['date'] as String?) ?? '',
        title: (j['title'] as String?) ?? 'Занятие',
        durationMin: (j['duration_min'] as num?)?.toInt() ?? 0,
        calories: (j['calories'] as num?)?.round(),
        caloriesEstimated: (j['calories_estimated'] as bool?) ?? false,
        addedByName: j['added_by_name'] as String?,
      );

  /// «40 мин» или «1 ч 20 мин»: в минутах длинное занятие читается плохо.
  String get durationLabel {
    if (durationMin < 60) return '$durationMin мин';
    final h = durationMin ~/ 60;
    final m = durationMin % 60;
    return m == 0 ? '$h ч' : '$h ч $m мин';
  }

  @override
  List<Object?> get props =>
      [id, date, title, durationMin, calories, caloriesEstimated, addedByName];
}
