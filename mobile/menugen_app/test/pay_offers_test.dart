// MG_PAYPERIOD / MG_PAYRELIABLE: выбор периода и исход оплаты в приложении.
//
// Оплата уходит во внешний браузер, и приложение о её исходе не узнаёт само:
// уведомление ЮKassa приходит на бэкенд. Поэтому по возвращении спрашиваем
// статус по идентификатору платежа — и он обязан пережить выгрузку приложения.
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:menugen_app/features/subscription/pay_offers.dart';
import 'package:menugen_app/features/subscription/pending_payment.dart';

final month = <String, dynamic>{
  'code': 'premium_month',
  'title': 'Месяц',
  'months': 1,
  'price': '299.00',
  'price_per_month': '299.00',
  'discount_percent': 0,
  'plan_code': 'premium',
};
final year = <String, dynamic>{
  'code': 'premium_year',
  'title': 'Год',
  'months': 12,
  'price': '2990.00',
  'price_per_month': '249.17',
  'discount_percent': 17,
  'plan_code': 'premium',
};
final freeOffer = <String, dynamic>{
  'code': 'free_month',
  'title': 'Месяц',
  'months': 1,
  'price': '0.00',
  'price_per_month': '0.00',
  'discount_percent': 0,
  'plan_code': 'free',
};

void main() {
  group('offersForPlan', () {
    test('берём периоды своего тарифа', () {
      expect(offersForPlan([month, year, freeOffer], 'premium'), [month, year]);
      expect(offersForPlan([month, year, freeOffer], 'free'), [freeOffer]);
    });

    test('тариф без периодов — покупать нечего', () {
      expect(offersForPlan([month], 'pro'), isEmpty);
      expect(offersForPlan([month], null), isEmpty);
    });
  });

  group('selectedOffer', () {
    test('выбранный период', () {
      expect(selectedOffer([month, year], 'premium_year'), year);
    });

    test('без выбора — первый (самый короткий)', () {
      expect(selectedOffer([month, year], null), month);
    });

    test('выбор устарел — не падаем', () {
      // Период выключили в админке, пока экран был открыт.
      expect(selectedOffer([month], 'premium_year'), month);
      expect(selectedOffer([], 'premium_year'), isNull);
    });
  });

  group('цена и выгода', () {
    test('цена без копеек', () {
      expect(offerPrice(year), '2990 ₽');
      expect(offerPrice(month), '299 ₽');
    });

    test('для длинного периода видно цену за месяц', () {
      expect(offerPriceNote(year), '249 ₽ в месяц');
    });

    test('для месяца сравнивать не с чем', () {
      expect(offerPriceNote(month), isNull);
    });

    test('скидку берём у бэкенда, не считаем сами', () {
      // Иначе цифры в приложении и в вебе разъедутся.
      expect(offerDiscount(year), 17);
      expect(offerDiscount(month), 0);
      expect(offerDiscount(const {}), 0);
    });
  });

  group('paymentResultText', () {
    test('успех называет срок', () {
      final r = paymentResultText({'status': 'succeeded', 'expires_at': '2027-08-16T10:00:00Z'});
      expect(r!.$1, contains('2027-08-16'));
      expect(r.$2, isTrue);
    });

    test('успех без срока — всё равно успех', () {
      final r = paymentResultText({'status': 'succeeded'});
      expect(r!.$2, isTrue);
    });

    test('отмена и возврат — не успех', () {
      expect(paymentResultText({'status': 'cancelled'})!.$2, isFalse);
      expect(paymentResultText({'status': 'refunded'})!.$2, isFalse);
    });

    test('платёж ещё в работе — говорить рано', () {
      // null означает «спросим ещё раз», а не «отменено».
      expect(paymentResultText({'status': 'pending'}), isNull);
      expect(paymentResultText(const {}), isNull);
    });
  });

  group('pendingPayment', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('идентификатор переживает выгрузку приложения', () async {
      await rememberPayment('pay-1');

      expect(await takePendingPayment(), 'pay-1');
    });

    test('результат показываем один раз', () async {
      await rememberPayment('pay-2');
      await takePendingPayment();

      expect(await takePendingPayment(), isNull);
    });

    test('без оплаты — ничего', () async {
      expect(await takePendingPayment(), isNull);
    });
  });
}
