// MG_PHONECODE: разбор номера и три способа его ввести.
//
// Проверяется ровно то, что легко сломать незаметно: склейка кода с номером
// (иначе получается «+7+7…»), вставка номера целиком и российская «восьмёрка».
// Внешний контроллер должен всегда держать полный номер — экраны входа и
// регистрации читают именно его.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:menugen_app/core/widgets/phone_field.dart';

Future<TextEditingController> _pump(WidgetTester tester, {String initial = defaultPhoneCode}) async {
  final controller = TextEditingController(text: initial);
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: PhoneField(controller: controller)),
  ));
  await tester.pump();
  return controller;
}

void main() {
  group('splitPhone', () {
    test('пустая строка — код по умолчанию', () {
      final r = splitPhone('');
      expect(r.code, '+7');
      expect(r.rest, '');
    });

    test('российский номер', () {
      final r = splitPhone('+79123456789');
      expect(r.code, '+7');
      expect(r.rest, '9123456789');
    });

    test('длинный код не съедается коротким', () {
      // «+375…» не должно разобраться как «+3» или «+37»: коды примеряются от
      // длинных к коротким.
      final r = splitPhone('+375291234567');
      expect(r.code, '+375');
      expect(r.rest, '291234567');
    });

    test('оформление номера отбрасывается', () {
      final r = splitPhone('+7 (912) 345-67-89');
      expect(r.code, '+7');
      expect(r.rest, '9123456789');
    });
  });

  group('PhoneField', () {
    testWidgets('код страны подставлен заранее', (tester) async {
      final controller = await _pump(tester);
      expect(controller.text, '+7');
      // В поле — только номер, без кода: код живёт в списке слева.
      expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, '');
    });

    testWidgets('набранные цифры склеиваются с кодом', (tester) async {
      final controller = await _pump(tester);
      await tester.enterText(find.byType(TextField), '9123456789');
      await tester.pump();
      expect(controller.text, '+79123456789');
    });

    testWidgets('вставка номера целиком не удваивает код', (tester) async {
      final controller = await _pump(tester);
      await tester.enterText(find.byType(TextField), '+375291234567');
      await tester.pump();
      expect(controller.text, '+375291234567');
    });

    testWidgets('восьмёрка вместо +7', (tester) async {
      final controller = await _pump(tester);
      await tester.enterText(find.byType(TextField), '89123456789');
      await tester.pump();
      expect(controller.text, '+79123456789');
    });

    testWidgets('готовый номер разбирается при открытии экрана', (tester) async {
      final controller = await _pump(tester, initial: '+375291234567');
      expect(controller.text, '+375291234567');
      // Код ушёл в список, в поле остался только сам номер.
      expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, '291234567');
    });
  });
}
