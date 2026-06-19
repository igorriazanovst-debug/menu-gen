import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import 'app_skin.dart';

// MG_SKIN: состояние выбранного скина. Источник истины при логине — профиль
// (user.ui_skin); локально дублируем в SharedPreferences для мгновенного
// применения и оффлайна.
class ThemeCubit extends Cubit<AppSkin> {
  static const _prefsKey = 'ui_skin';

  final SharedPreferences prefs;
  final ApiClient apiClient;

  ThemeCubit({required this.prefs, required this.apiClient})
      : super(appSkinFromCode(prefs.getString(_prefsKey)));

  /// Применить скин из профиля (после логина/проверки) без записи в API.
  void loadFromProfile(Map<String, dynamic> user) {
    final skin = appSkinFromCode(user['ui_skin'] as String?);
    prefs.setString(_prefsKey, skin.code);
    if (skin != state) emit(skin);
  }

  /// Пользователь сменил скин: применяем локально и синкаем в аккаунт.
  Future<void> setSkin(AppSkin skin) async {
    if (skin == state) return;
    await prefs.setString(_prefsKey, skin.code);
    emit(skin);
    try {
      await apiClient.patch('/users/me/', data: {'ui_skin': skin.code});
    } catch (_) {
      // оффлайн/ошибка — локально применено, синк догонит при следующей смене
    }
  }
}
