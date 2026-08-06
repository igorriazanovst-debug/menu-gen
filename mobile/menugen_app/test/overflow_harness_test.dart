// MG_NOOVERFLOW: сторож против «RIGHT OVERFLOWED BY N PIXELS».
//
// Переполнение возникает во время раскладки, статический анализатор его не
// видит. Поэтому проверяем иначе: рендерим виджеты, которые показывают данные,
// с нарочно длинными строками на узком экране — и падаем при любом
// переполнении. В release-сборке полоски не видно, текст просто обрезается, так
// что поймать проблему можно только здесь.
//
// Новый виджет, показывающий текст из базы, стоит добавлять сюда же. Виджеты,
// которым нужны блоки состояния (например SyncIndicator), сюда не попадают —
// их поднимать дороже, чем они того стоят.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/core/widgets/icon_label.dart';
import 'package:menugen_app/features/recipes/widgets/ingredient_row.dart';

/// Строки, на которых обычно ломается вёрстка: длинное название из базы,
/// количество с уточнением, единица измерения словами.
const longName = 'Перец болгарский красный крупный сладкий очищенный от семян';
const longAmount = '2 стакана (или 300 г замороженной кукурузы)';

/// Самый узкий экран, который стоит поддерживать: iPhone SE / бюджетные Android.
const narrow = 320.0;

Future<void> pumpNarrow(WidgetTester tester, Widget child, {double width = narrow}) async {
  tester.view.physicalSize = Size(width, 800);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: Scaffold(body: SingleChildScrollView(child: child)),
  ));
  await tester.pump();
}

void main() {
  group('строка ингредиента', () {
    testWidgets('длинные название и количество', (tester) async {
      await pumpNarrow(tester, const RecipeIngredientRow(name: longName, amount: longAmount));

      expect(tester.takeException(), isNull);
    });
  });

  group('иконка с подписью', () {
    testWidgets('длинная подпись сжимается', (tester) async {
      await pumpNarrow(
        tester,
        const IconLabel(icon: Icons.schedule, text: '1 час 30 минут в мультиварке на медленном огне'),
      );

      expect(tester.takeException(), isNull);
    });

    testWidgets('несколько подписей в одной строке', (tester) async {
      // так они и стоят в карточке рецепта: время, порции, кухня
      await pumpNarrow(
        tester,
        const Row(
          children: [
            Flexible(child: IconLabel(icon: Icons.schedule, text: '1 час 30 минут в мультиварке')),
            SizedBox(width: 8),
            Flexible(child: IconLabel(icon: Icons.people, text: '6 порций для большой семьи')),
          ],
        ),
      );

      expect(tester.takeException(), isNull);
    });
  });

}
