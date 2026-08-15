// MG_EMAILVERIFY_MOBILE: регистрация больше не всегда заканчивается входом.
//
// При включённом EMAIL_VERIFICATION_REQUIRED бэкенд отвечает на регистрацию
// 201-м, но БЕЗ токенов: вместо них `requires_email_verification` и адрес, на
// который ушло письмо. Приложение читало `data['access'] as String`
// безусловно — падало на null и показывало «Не удалось войти», хотя аккаунт
// создан и письмо отправлено.
//
// Признак смотрим по двум полям сразу: `requires_email_verification` — явный
// флаг, отсутствие `access` — то, из-за чего ломался вход. Второго достаточно
// и без первого: без токена входить всё равно нечем.
import '../../core/api/api_exception.dart';

/// Ответ регистрации не содержит токенов — нужно подтвердить e-mail.
bool needsEmailVerification(Map<String, dynamic> data) {
  if (data['requires_email_verification'] == true) return true;
  final access = data['access'];
  return access is! String || access.isEmpty;
}

/// Адрес, на который ушло письмо. Бэкенд возвращает его в ответе; если вдруг
/// не вернул — показываем тот, что ввёл пользователь.
String verificationEmail(Map<String, dynamic> data, String fallback) {
  final email = data['email'];
  return (email is String && email.isNotEmpty) ? email : fallback;
}

/// Вход отклонён из-за неподтверждённого адреса — возвращает этот адрес.
/// null — отказ по любой другой причине.
///
/// Тот же случай, что и после регистрации: аккаунт есть, письмо нужно. Поэтому
/// состояние одно на оба входа в ситуацию, а не два похожих.
String? pendingVerificationEmail(Object error, String fallback) {
  if (error is! ApiException || error.errorCode != 'email_not_verified') {
    return null;
  }
  final body = error.body;
  final email = body is Map ? body['email'] : null;
  return (email is String && email.isNotEmpty) ? email : fallback;
}
