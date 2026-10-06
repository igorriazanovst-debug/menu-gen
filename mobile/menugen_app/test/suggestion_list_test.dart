// MG_SUGGEST: список подсказок под полем поиска.
//
// Проверяется то, из-за чего список и переделывали: человек не понимал, что
// это всплывшая подсказка, почему строка нашлась и что ниже есть ещё.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/core/widgets/suggestion_list.dart';

Future<void> _pump(
  WidgetTester tester, {
  required List<SuggestionItem> items,
  String query = '',
  SuggestionAction? action,
  String? emptyText,
}) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(), // виджет берёт цвета из скин-токенов
    home: Scaffold(
      body: Center(
        child: SizedBox(
          width: 360,
          child: SuggestionList(
            items: items,
            query: query,
            action: action,
            emptyText: emptyText,
          ),
        ),
      ),
    ),
  ));
  await tester.pump();
}

SuggestionItem _it(String title, {String? subtitle, String? trailing, VoidCallback? onTap}) =>
    SuggestionItem(title: title, subtitle: subtitle, trailing: trailing, onTap: onTap ?? () {});

void main() {
  group('splitMatch', () {
    test('находит совпадение в начале', () {
      expect(SuggestionList.splitMatch('Творог 5%', 'творог'), ['', 'Творог', ' 5%']);
    });

    test('находит совпадение в середине слова', () {
      // Ради этого подсветка и нужна: иначе непонятно, почему «творожная
      // масса» нашлась по запросу «творож».
      expect(SuggestionList.splitMatch('Творожная масса', 'творож'), ['', 'Творож', 'ная масса']);
    });

    test('регистр не важен', () {
      expect(SuggestionList.splitMatch('МОЛОКО', 'мол')?[1], 'МОЛ');
    });

    test('ё и е считаются одной буквой', () {
      // В каталоге соседствуют «Свёкла» и «Свекла»; подсветка не должна
      // зависеть от того, как человек набрал.
      expect(SuggestionList.splitMatch('Свёкла варёная', 'свекла'), ['', 'Свёкла', ' варёная']);
    });

    test('нет совпадения — нечего подсвечивать', () {
      expect(SuggestionList.splitMatch('Молоко', 'кефир'), isNull);
    });

    test('пустой запрос ничего не подсвечивает', () {
      expect(SuggestionList.splitMatch('Молоко', ''), isNull);
      expect(SuggestionList.splitMatch('Молоко', '   '), isNull);
    });
  });

  group('SuggestionList', () {
    testWidgets('показывает находки и их число', (tester) async {
      await _pump(tester, items: [_it('Творог 5%'), _it('Творог 9%')], query: 'творог');

      expect(find.text('Найдено 2'), findsOneWidget);
      expect(find.textContaining('5%'), findsOneWidget);
    });

    testWidgets('по строке можно нажать', (tester) async {
      var picked = false;
      await _pump(tester, items: [_it('Творог 5%', onTap: () => picked = true)]);

      await tester.tap(find.textContaining('Творог 5%'));
      await tester.pump();

      expect(picked, isTrue);
    });

    testWidgets('подпись и значение справа показываются', (tester) async {
      await _pump(tester, items: [_it('Творог домашний', subtitle: 'своё', trailing: '150 ккал')]);

      expect(find.text('своё'), findsOneWidget);
      expect(find.text('150 ккал'), findsOneWidget);
    });

    testWidgets('пустой список без действия и текста не рисуется', (tester) async {
      await _pump(tester, items: const []);

      expect(find.byType(Scrollbar), findsNothing);
      expect(find.textContaining('Найдено'), findsNothing);
    });

    testWidgets('когда искали и не нашли — говорим об этом', (tester) async {
      // Молчание человек читает как «приложение не отвечает».
      await _pump(tester, items: const [], emptyText: 'Ничего не нашлось');

      expect(find.text('Ничего не нашлось'), findsOneWidget);
    });

    testWidgets('действие внизу нажимается и видно без находок', (tester) async {
      var added = false;
      await _pump(
        tester,
        items: const [],
        action: SuggestionAction(label: 'Добавить «творог» как новый', onTap: () => added = true),
      );

      await tester.tap(find.textContaining('как новый'));
      await tester.pump();

      expect(added, isTrue);
    });

    testWidgets('длинное название не ломает строку', (tester) async {
      // MG_NOOVERFLOW: в каталоге есть названия на полсотни букв.
      await _pump(tester, items: [
        _it('Сибас, фаршированный гремолатой, запеченный с овощами и картофелем',
            trailing: '164 ккал'),
      ]);

      expect(tester.takeException(), isNull);
    });

    testWidgets('список прокручивается, когда находок много', (tester) async {
      await _pump(tester, items: [for (var i = 0; i < 30; i++) _it('Продукт $i')]);

      expect(find.byType(Scrollbar), findsOneWidget);
      expect(find.text('Найдено 30'), findsOneWidget);
    });
  });
}
