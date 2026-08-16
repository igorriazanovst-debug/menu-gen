// MG_PAYRELIABLE: чем закончилась оплата, начатая в приложении.
//
// Оплата уходит во внешний браузер, и приложение о её исходе ничего не знает.
// Уведомление от ЮKassa приходит на бэкенд, а не сюда, и может опоздать —
// поэтому по возвращении спрашиваем статус сами, по идентификатору платежа.
//
// Идентификатор переживает выгрузку приложения из памяти: пока человек платит,
// система вполне может его прибить.
import 'package:shared_preferences/shared_preferences.dart';

const _key = 'pending_payment_id';

Future<void> rememberPayment(String paymentId) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(_key, paymentId);
}

/// Возвращает идентификатор и забывает его — результат показываем один раз.
Future<String?> takePendingPayment() async {
  final prefs = await SharedPreferences.getInstance();
  final id = prefs.getString(_key);
  if (id != null) await prefs.remove(_key);
  return (id != null && id.isNotEmpty) ? id : null;
}

/// Текст результата по ответу /payments/<id>/status/.
///
/// Возвращает (текст, успех). null — платёж ещё в работе и говорить рано.
(String, bool)? paymentResultText(Map<String, dynamic> status) {
  switch (status['status']) {
    case 'succeeded':
      final until = status['expires_at']?.toString();
      final date = (until != null && until.length >= 10) ? until.substring(0, 10) : null;
      return (
        date == null ? 'Оплата прошла — премиум активен.' : 'Оплата прошла — премиум до $date.',
        true,
      );
    case 'cancelled':
      return ('Оплата отменена.', false);
    case 'refunded':
      return ('Платёж возвращён.', false);
    default:
      return null; // pending — ждём, повторим позже
  }
}
