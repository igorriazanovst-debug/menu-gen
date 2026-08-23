// MG_SELFUPDATE: когда предлагать обновление.
import 'package:flutter_test/flutter_test.dart';
import 'package:menugen_app/core/update/update_policy.dart';

void main() {
  final now = DateTime(2026, 8, 24, 12, 0);

  group('selfUpdateAllowed', () {
    test('магазинная сборка себя не обновляет', () {
      expect(selfUpdateAllowed(flag: false, installerStore: null), isFalse);
    });

    test('копия из магазина не обновляется, даже если флаг включён', () {
      // Страховка от ошибки сборки: сайтовый артефакт уехал в магазин.
      expect(selfUpdateAllowed(flag: true, installerStore: 'ru.vk.store'), isFalse);
      expect(selfUpdateAllowed(flag: true, installerStore: 'com.android.vending'), isFalse);
    });

    test('копия с сайта обновляется', () {
      expect(selfUpdateAllowed(flag: true, installerStore: null), isTrue);
      expect(selfUpdateAllowed(flag: true, installerStore: 'com.android.chrome'), isTrue);
    });
  });

  group('shouldOfferUpdate', () {
    test('новая версия — предлагаем', () {
      expect(
        shouldOfferUpdate(installedCode: 2, latestCode: 3, now: now),
        isTrue,
      );
    });

    test('та же или более старая версия — молчим', () {
      expect(shouldOfferUpdate(installedCode: 3, latestCode: 3, now: now), isFalse);
      expect(shouldOfferUpdate(installedCode: 3, latestCode: 2, now: now), isFalse);
    });

    test('без номера сборки сравнивать нечего', () {
      expect(shouldOfferUpdate(installedCode: 2, latestCode: null, now: now), isFalse);
    });

    test('отложенную версию не навязываем', () {
      expect(
        shouldOfferUpdate(installedCode: 2, latestCode: 3, skippedCode: 3, now: now),
        isFalse,
      );
    });

    test('но следующую после отложенной — предлагаем', () {
      expect(
        shouldOfferUpdate(installedCode: 2, latestCode: 4, skippedCode: 3, now: now),
        isTrue,
      );
    });

    test('чаще раза в сутки не напоминаем', () {
      expect(
        shouldOfferUpdate(
          installedCode: 2,
          latestCode: 3,
          lastPromptAt: now.subtract(const Duration(hours: 5)),
          now: now,
        ),
        isFalse,
      );
    });

    test('через сутки напоминаем снова', () {
      expect(
        shouldOfferUpdate(
          installedCode: 2,
          latestCode: 3,
          lastPromptAt: now.subtract(const Duration(hours: 25)),
          now: now,
        ),
        isTrue,
      );
    });
  });
}
