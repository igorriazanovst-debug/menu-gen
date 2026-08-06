// MG_LOGINFIX: текст ошибки входа, понятный пользователю.
//
// Раньше на экран уходил `e.toString()` — то есть
// «ApiException(status=403, code=email_not_verified, message=…)». По такому
// сообщению нельзя ни понять, что делать, ни внятно рассказать о проблеме:
// именно так выглядел «просто не работает вход».
//
// Здесь каждый случай назван своими словами, а причина, которую прислал
// бэкенд, сохраняется — без неё разбираться с чужим устройством вслепую.
import '../../core/api/api_exception.dart';

String authErrorText(Object error) {
  if (error is! ApiException) return 'Не удалось войти. Попробуйте ещё раз.';

  if (error.isNetwork) {
    return 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.';
  }
  // Гейт подтверждения e-mail: аккаунт есть, пароль верный, но вход закрыт.
  if (error.errorCode == 'email_not_verified') {
    return 'E-mail не подтверждён — вход закрыт. Подтвердите адрес по ссылке '
        'из письма или напишите в поддержку.';
  }
  if (error.statusCode == 400) {
    // Сюда попадает и «Неверные учётные данные», и претензии к формату полей.
    return error.message;
  }
  if (error.isUnauthorized) {
    return 'Неверный e-mail (телефон) или пароль.';
  }
  if (error.isThrottled) {
    return 'Слишком много попыток входа. Подождите минуту и попробуйте снова.';
  }
  if (error.isServerError) {
    return 'Сервер не отвечает (${error.statusCode}). Попробуйте позже.';
  }
  return '${error.message} (${error.statusCode})';
}
