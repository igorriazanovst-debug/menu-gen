import 'package:freezed_annotation/freezed_annotation.dart';
part 'diary_entry.freezed.dart';
part 'diary_entry.g.dart';

@freezed
class DiaryEntry with _$DiaryEntry {
  const factory DiaryEntry({
    required int id,
    required String date,
    required String mealType,
    int? recipe,
    String? recipeTitle,
    String? customName,
    @Default({}) Map<String, dynamic> nutrition,
    @Default(1.0) double quantity,
  }) = _DiaryEntry;

  factory DiaryEntry.fromJson(Map<String, dynamic> json) => _$DiaryEntryFromJson(json);
}
