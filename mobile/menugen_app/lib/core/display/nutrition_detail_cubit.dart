// MG_NUTRIDETAIL: состояние настройки подробности чисел.
//
// Устроено как ThemeCubit (MG_SKIN) и по той же причине: источник истины —
// аккаунт (Profile.nutrition_detail), локально дублируем в SharedPreferences,
// чтобы выбор применялся мгновенно и пережил запуск без сети.
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import 'nutrition_detail.dart';

class NutritionDetailCubit extends Cubit<NutritionDetail> {
  static const _prefsKey = 'nutrition_detail';

  final SharedPreferences prefs;
  final ApiClient apiClient;

  NutritionDetailCubit({required this.prefs, required this.apiClient})
      : super(nutritionDetailFromCode(prefs.getString(_prefsKey)));

  /// Применить выбор из профиля (после входа) без записи в API.
  void loadFromProfile(Map<String, dynamic> user) {
    final profile = user['profile'];
    final code = profile is Map ? profile['nutrition_detail'] as String? : null;
    // Профиль без поля — сервер старше приложения. Тогда ничего не трогаем:
    // перетереть локальный выбор умолчанием значит отменить его молча.
    if (code == null) return;
    final value = nutritionDetailFromCode(code);
    prefs.setString(_prefsKey, value.code);
    if (value != state) emit(value);
  }

  /// Человек сменил подробность: применяем сразу, синкаем в аккаунт.
  Future<void> set(NutritionDetail value) async {
    if (value == state) return;
    await prefs.setString(_prefsKey, value.code);
    emit(value);
    try {
      await apiClient.patch('/users/me/', data: {
        'profile': {'nutrition_detail': value.code}
      });
    } catch (_) {
      // Оффлайн или отказ — локально уже применено, синк догонит при
      // следующей смене. Откатывать показ назад было бы хуже: человек видит,
      // что настройка не сработала, хотя она сработала.
    }
  }
}
