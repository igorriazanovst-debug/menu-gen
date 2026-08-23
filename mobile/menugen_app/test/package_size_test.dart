// MG_DIARYSCAN: фасовка из справочника → граммы для дневника.
import 'package:flutter_test/flutter_test.dart';
import 'package:menugen_app/core/utils/package_size.dart';

void main() {
  group('packageGrams', () {
    test('граммы и миллилитры берутся как есть', () {
      expect(packageGrams('250г'), 250);
      expect(packageGrams('930мл'), 930);
      expect(packageGrams('300 г'), 300);
    });

    test('килограммы и литры переводятся', () {
      expect(packageGrams('1кг'), 1000);
      expect(packageGrams('1,5л'), 1500);
    });

    test('пачка из нескольких пакетиков считается целиком', () {
      expect(packageGrams('4.5г x 4 шт'), 18);
      expect(packageGrams('2г х 25шт'), 50);
    });

    test('нечитаемая фасовка — не повод выдумывать число', () {
      expect(packageGrams('упак'), isNull);
      expect(packageGrams(''), isNull);
      expect(packageGrams(null), isNull);
      expect(packageGrams('шт'), isNull);
    });

    test('нелепые величины отбрасываются', () {
      expect(packageGrams('50кг'), isNull);
    });

    test('размер вытаскивается из хвоста названия', () {
      expect(packageGrams('Молоко Простоквашино 3.2%, 930мл'), 930);
    });
  });
}
