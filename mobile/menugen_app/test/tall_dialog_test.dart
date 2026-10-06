// MG_TALLDIALOG: диалог с поиском и поднятой клавиатурой.
//
// Проверяется ровно то, что доехало до телефона и было видно только там: с
// поднятой клавиатурой диалог сжимался, и от списка подсказок оставалась одна
// строка, обрезанная посередине. Тестами это не ловилось, потому что они
// разворачивали виджет на экране без клавиатуры.
//
// Поэтому здесь экран задаётся как у настоящего телефона (393×873 точки,
// 1080×2400 при плотности 2.75) и отдельно поднимается клавиатура на 320
// точек. Числа ниже — не красота, а порог читаемости: меньше трёх строк в
// списке человек воспринимает как «ничего не нашлось».
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/core/widgets/suggestion_list.dart';
import 'package:menugen_app/core/widgets/tall_dialog.dart';

const double _screenW = 393;
const double _screenH = 873;
const double _dpr = 2.75;
const double _keyboard = 320;

/// Разворачивает диалог на телефонном экране, при желании с клавиатурой.
Future<void> _pump(WidgetTester tester, {double keyboard = 0, int items = 20}) async {
  tester.view.devicePixelRatio = _dpr;
  tester.view.physicalSize = const Size(_screenW * _dpr, _screenH * _dpr);
  tester.view.viewInsets = FakeViewPadding(bottom: keyboard * _dpr);
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: TallDialog(
      title: 'Добавить в дневник',
      actions: [
        TextButton(onPressed: () {}, child: const Text('Отмена')),
        FilledButton(onPressed: () {}, child: const Text('Добавить')),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const TextField(decoration: InputDecoration(labelText: 'Поиск продукта (от 2 букв)')),
          Flexible(
            child: SuggestionList(
              query: 'ябл',
              maxHeight: double.infinity,
              items: [
                for (var i = 0; i < items; i++)
                  SuggestionItem(title: 'Яблоко сорт $i', trailing: '52 ккал', onTap: () {}),
              ],
            ),
          ),
        ],
      ),
    ),
  ));
  await tester.pumpAndSettle();
}

double _boxHeight(WidgetTester tester) => tester.getSize(find.byKey(TallDialog.boxKey)).height;

void main() {
  group('TallDialog', () {
    testWidgets('без клавиатуры занимает почти весь экран', (tester) async {
      await _pump(tester);

      // 873 минус поля по 12 сверху и снизу.
      expect(_boxHeight(tester), closeTo(_screenH - 24, 1));
    });

    testWidgets('с клавиатурой теряет её высоту и ни точкой больше', (tester) async {
      await _pump(tester, keyboard: _keyboard);

      // Это и есть суть починки: раньше здесь оставалась коробка в 440 точек,
      // которой негде было поместиться, и содержимое резалось.
      expect(_boxHeight(tester), closeTo(_screenH - _keyboard - 24, 1));
    });

    testWidgets('с клавиатурой в списке видно не меньше пяти строк', (tester) async {
      await _pump(tester, keyboard: _keyboard);

      for (var i = 0; i < 5; i++) {
        expect(find.textContaining('Яблоко сорт $i'), findsOneWidget, reason: 'строка $i не нарисована');
      }
    });

    testWidgets('с клавиатурой список не обрезан снизу экраном', (tester) async {
      await _pump(tester, keyboard: _keyboard);

      // Низ списка должен быть выше верха клавиатуры. Проверяется именно это,
      // а не «виджет существует»: обрезанная строка в дереве есть, а на
      // экране её нет.
      final bottom = tester.getRect(find.byType(SuggestionList)).bottom;
      expect(bottom, lessThanOrEqualTo(_screenH - _keyboard));
    });

    testWidgets('список забирает остаток высоты, а не 220 точек', (tester) async {
      await _pump(tester, keyboard: _keyboard);

      // До починки список упирался в 220 точек даже там, где место было.
      expect(tester.getSize(find.byType(SuggestionList)).height, greaterThan(260));
    });

    testWidgets('коротких находок не растягиваем на весь экран', (tester) async {
      await _pump(tester, items: 2);

      // Обратная сторона: две находки не должны раздувать панель во весь
      // диалог — иначе список выглядит как отдельная страница.
      expect(tester.getSize(find.byType(SuggestionList)).height, lessThan(200));
    });

    testWidgets('на маленьком экране с клавиатурой не ужимается в щель', (tester) async {
      tester.view.devicePixelRatio = 2;
      tester.view.physicalSize = const Size(320 * 2, 480 * 2);
      tester.view.viewInsets = FakeViewPadding(bottom: 300 * 2);
      addTearDown(tester.view.reset);

      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light(),
        home: const TallDialog(title: 'Узко', child: SizedBox.shrink()),
      ));
      await tester.pumpAndSettle();

      // 480 − 300 − 24 = 156, и это уже не диалог. Держим нижний предел:
      // пусть лучше уедет под клавиатуру, чем покажет щель.
      expect(_boxHeight(tester), 260);
    });
  });
}
