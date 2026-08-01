// MG_APPICON: сторож для фирменного SVG.
//
// flutter_svg не поддерживает CSS-таблицы стилей: если цвета описаны классами
// (<style> с .fil0/.str0 — так их отдаёт экспорт CorelDRAW), знак рисуется
// сплошным чёрным. В браузере при этом всё выглядит правильно, поэтому поломку
// легко не заметить. Цвета должны лежать в атрибутах фигур.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final logo = File('assets/images/logo.svg');

  test('логотип на месте', () {
    expect(logo.existsSync(), isTrue, reason: 'assets/images/logo.svg не найден');
  });

  test('цвета заданы атрибутами, а не CSS-классами', () {
    final svg = logo.readAsStringSync();

    expect(svg.contains('<style'), isFalse,
        reason: 'flutter_svg игнорирует <style> — знак станет чёрным. '
            'Разложите цвета из классов по атрибутам fill/stroke.');
    expect(RegExp(r'\sclass\s*=').hasMatch(svg), isFalse,
        reason: 'Остались ссылки на CSS-классы — цвета не применятся.');
    expect(svg.contains('fill="#46702E"'), isTrue, reason: 'Потерян фирменный зелёный колец и точек.');
    expect(svg.contains('fill="url(#id0)"'), isTrue, reason: 'Потерян градиент листьев.');
  });

  testWidgets('flutter_svg рисует логотип без ошибок', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Center(child: SvgPicture.string(logo.readAsStringSync(), height: 96)),
    ));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byType(SvgPicture), findsOneWidget);
  });
}
