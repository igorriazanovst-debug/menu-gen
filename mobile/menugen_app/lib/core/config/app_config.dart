class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  /// MG_LOGINFIX: адрес сервера человеческим языком — «menugen.ru» или
  /// «31.192.110.121:8003».
  ///
  /// Адрес зашивается в сборку (--dart-define), и по установленному apk понять,
  /// куда он ходит, нельзя никак. А это первое, что нужно знать, когда «не
  /// работает вход»: аккаунты dev и прод — разные базы, пароль от одной к другой
  /// не подходит. Поэтому в отладочных сборках адрес видно на экране входа.
  static String get apiHost {
    final uri = Uri.tryParse(apiBaseUrl);
    if (uri == null || uri.host.isEmpty) return apiBaseUrl;
    return uri.hasPort ? '${uri.host}:${uri.port}' : uri.host;
  }
}
