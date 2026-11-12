// MG_NUTRIDETAIL + MG_FOODSCALE: настройки отображения еды.
//
// Обе живут в аккаунте (Profile.nutrition_detail, Profile.food_text_scale) и
// одним состоянием, а не двумя кубитами: иначе чтение профиля, запись в
// SharedPreferences и синк в API были бы написаны дважды — и однажды
// разошлись бы.
//
// Устроено как ThemeCubit (MG_SKIN): источник истины — аккаунт, локально
// дублируем, чтобы выбор применялся мгновенно и пережил запуск без сети.
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import 'food_text_scale.dart';
import 'nutrition_detail.dart';

class DisplayPrefs extends Equatable {
  final NutritionDetail detail;
  final FoodTextScale scale;

  const DisplayPrefs({required this.detail, required this.scale});

  @override
  List<Object?> get props => [detail, scale];
}

class DisplayPrefsCubit extends Cubit<DisplayPrefs> {
  static const _detailKey = 'nutrition_detail';
  static const _scaleKey = 'food_text_scale';

  final SharedPreferences prefs;
  final ApiClient apiClient;

  DisplayPrefsCubit({required this.prefs, required this.apiClient})
      : super(DisplayPrefs(
          detail: nutritionDetailFromCode(prefs.getString(_detailKey)),
          scale: foodTextScaleFromCode(prefs.getString(_scaleKey)),
        ));

  /// Применить выбор из профиля (после входа) без записи в API.
  void loadFromProfile(Map<String, dynamic> user) {
    final profile = user['profile'];
    if (profile is! Map) return;
    // Поля может не быть: сервер старше приложения. Тогда не трогаем —
    // перетереть локальный выбор умолчанием значит отменить его молча.
    final detail = profile['nutrition_detail'] as String?;
    final scale = profile['food_text_scale'] as String?;
    var next = state;
    if (detail != null) {
      prefs.setString(_detailKey, nutritionDetailFromCode(detail).code);
      next = DisplayPrefs(detail: nutritionDetailFromCode(detail), scale: next.scale);
    }
    if (scale != null) {
      prefs.setString(_scaleKey, foodTextScaleFromCode(scale).code);
      next = DisplayPrefs(detail: next.detail, scale: foodTextScaleFromCode(scale));
    }
    if (next != state) emit(next);
  }

  Future<void> setDetail(NutritionDetail value) async {
    if (value == state.detail) return;
    await prefs.setString(_detailKey, value.code);
    emit(DisplayPrefs(detail: value, scale: state.scale));
    await _sync({'nutrition_detail': value.code});
  }

  Future<void> setScale(FoodTextScale value) async {
    if (value == state.scale) return;
    await prefs.setString(_scaleKey, value.code);
    emit(DisplayPrefs(detail: state.detail, scale: value));
    await _sync({'food_text_scale': value.code});
  }

  Future<void> _sync(Map<String, dynamic> patch) async {
    try {
      await apiClient.patch('/users/me/', data: {'profile': patch});
    } catch (_) {
      // Оффлайн или отказ — локально уже применено, синк догонит при
      // следующей смене. Откатывать показ назад было бы хуже: человек видит,
      // что настройка не сработала, хотя она сработала.
    }
  }
}
