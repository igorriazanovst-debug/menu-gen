// MG_SKIN: скины оформления приложения. Синкаются web↔mobile через аккаунт
// (поле user.ui_skin в /users/me/).

enum AppSkin { main, second }

extension AppSkinX on AppSkin {
  /// Строковый код для API/persist (совпадает с backend UISkin).
  String get code => this == AppSkin.second ? 'second' : 'main';

  String get label => this == AppSkin.second ? 'Альтернативная' : 'Основная';
}

AppSkin appSkinFromCode(String? code) =>
    code == 'second' ? AppSkin.second : AppSkin.main;
