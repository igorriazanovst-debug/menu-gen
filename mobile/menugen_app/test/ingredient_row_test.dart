// MG_INGROW: строка ингредиента не должна вылезать за край карточки.
//
// В рецепте «Кукурузное рагу с перцем и кабачками» длинное количество ломало
// вёрстку: Flutter рисовал «RIGHT OVERFLOWED BY 25 PIXELS», список разъезжался.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/recipes/widgets/ingredient_row.dart';

Future<void> _pump(
  WidgetTester tester, {
  required String name,
  required String amount,
  double width = 360,
}) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(), // виджет берёт цвета из скин-токенов
    home: Scaffold(
      body: Center(
        child: SizedBox(
          width: width,
          child: RecipeIngredientRow(name: name, amount: amount),
        ),
      ),
    ),
  ));
  await tester.pump();
}

void main() {
  group('amountOf', () {
    test('склеивает количество и единицу', () {
      expect(RecipeIngredientRow.amountOf({'quantity': '300', 'unit': 'г'}), '300 г');
    });

    test('пропускает пустые части', () {
      expect(RecipeIngredientRow.amountOf({'quantity': '2', 'unit': ''}), '2');
      expect(RecipeIngredientRow.amountOf({'quantity': '', 'unit': 'по вкусу'}), 'по вкусу');
      expect(RecipeIngredientRow.amountOf({}), '');
    });

    test('числовое количество приводится к строке', () {
      expect(RecipeIngredientRow.amountOf({'quantity': 300, 'unit': 'г'}), '300 г');
    });
  });

  group('вёрстка строки', () {
    testWidgets('длинное количество не вызывает переполнение', (tester) async {
      await _pump(
        tester,
        name: 'Кукуруза консервированная',
        amount: '2 стакана (или 300 г замороженной)',
      );

      expect(tester.takeException(), isNull);
    });

    testWidgets('длинное название тоже не ломает строку', (tester) async {
      await _pump(
        tester,
        name: 'Перец болгарский красный крупный сладкий очищенный от семян',
        amount: '3 шт',
      );

      expect(tester.takeException(), isNull);
    });

    testWidgets('узкий экран выдерживает оба длинных поля', (tester) async {
      await _pump(
        tester,
        name: 'Кабачки молодые нарезанные кубиками',
        amount: '500 г (примерно два средних)',
        width: 240,
      );

      expect(tester.takeException(), isNull);
    });

    testWidgets('обычная строка показывает название и количество', (tester) async {
      await _pump(tester, name: 'Кукуруза', amount: '300 г');

      expect(find.text('Кукуруза'), findsOneWidget);
      expect(find.text('300 г'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('без количества рисуется только название', (tester) async {
      await _pump(tester, name: 'Соль', amount: '');

      expect(find.text('Соль'), findsOneWidget);
      expect(find.byType(ConstrainedBox), findsWidgets); // сам виджет не падает
      expect(tester.takeException(), isNull);
    });

    testWidgets('количество занимает не больше своей доли строки', (tester) async {
      await _pump(
        tester,
        name: 'Кукуруза',
        amount: '2 стакана (или 300 г замороженной)',
        width: 360,
      );

      final amountWidth = tester.getSize(find.text('2 стакана (или 300 г замороженной)')).width;
      // 40% ширины строки минус внутренние отступы контейнера (12+12)
      expect(amountWidth, lessThanOrEqualTo((360 - 24) * 0.4 + 1));
    });
  });
}
