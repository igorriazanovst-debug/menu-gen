// MG_KBJUMATCH: экран «Мои продукты» и пустое КБЖУ.
//
// Случай с прода: человек завёл свой продукт «фарш телятина» и остался без
// чисел, хотя в каталоге лежит «Фарш из телятины» с 220 ккал. Обычный поиск
// его не показал — он требует слова подряд и в том же порядке, а между ними
// стоит «из».
//
// Проверяется то, что человек видит: что про дыру ему сказали, и что чужие
// числа в его запись сами собой не попали.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/fridge/screens/my_products_screen.dart';

class _MockApi extends Mock implements ApiClient {}

final _gapped = {
  'id': 1810,
  'name': 'фарш телятина',
  'calories_per_100g': null,
  'nutrition': {},
  'category_id': null,
  'category_name': 'Мясо',
  'fridge_usage': 0,
};

final _filled = {
  'id': 243,
  'name': 'Плюмбус домашний',
  'calories_per_100g': '150.00',
  'nutrition': {'proteins': 16, 'fats': 8, 'carbs': 2},
  'category_id': null,
  'category_name': 'Мясо',
  'fridge_usage': 0,
};

final _suggestion = {
  'suggestions': [
    {
      'id': 243,
      'name': 'Фарш из телятины',
      'calories_per_100g': '220.00',
      'nutrition': {'proteins': 18.3, 'fats': 18.4, 'carbs': 0.0},
      'category_id': null,
      'match': 1.0,
    }
  ]
};

Future<void> _open(WidgetTester tester, ApiClient api) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: MyProductsScreen(apiClient: api),
  ));
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() => registerFallbackValue(<String, dynamic>{}));

  late _MockApi api;

  setUp(() {
    api = _MockApi();
    when(() => api.get('/fridge/categories/')).thenAnswer((_) async => const []);
    when(() => api.get('/fridge/products/kbju-suggest/', params: any(named: 'params')))
        .thenAnswer((_) async => Map<String, dynamic>.from(_suggestion));
  });

  void withProducts(List<Map<String, dynamic>> items) {
    when(() => api.get('/fridge/products/', params: any(named: 'params'))).thenAnswer((_) async => items);
  }

  testWidgets('про запись без КБЖУ человеку говорят', (tester) async {
    withProducts([_gapped]);

    await _open(tester, api);

    expect(find.text('У одного продукта не указано КБЖУ'), findsOneWidget);
    expect(find.text('Заполнить'), findsOneWidget);
  });

  testWidgets('когда всё заполнено, плашки нет', (tester) async {
    withProducts([_filled]);

    await _open(tester, api);

    expect(find.textContaining('не указано КБЖУ'), findsNothing);
  });

  testWidgets('во множественном числе счёт верный', (tester) async {
    withProducts([_gapped, {..._gapped, 'id': 1811, 'name': 'квазибрикус'}]);

    await _open(tester, api);

    expect(find.text('У 2 продуктов не указано КБЖУ'), findsOneWidget);
  });

  testWidgets('лист показывает, что именно подставится', (tester) async {
    withProducts([_gapped]);
    await _open(tester, api);

    await tester.tap(find.text('Заполнить'));
    await tester.pumpAndSettle();

    expect(find.text('Заполнить КБЖУ из каталога'), findsOneWidget);
    expect(find.text('→ Фарш из телятины'), findsOneWidget);
    expect(find.textContaining('220 ккал'), findsOneWidget);
  });

  testWidgets('сам по себе лист ничего не пишет', (tester) async {
    // Это записи человека: пустое КБЖУ там может значить «мой фарш не такой,
    // как в каталоге». Молчаливая подстановка разошлась бы по дневнику и меню.
    withProducts([_gapped]);
    await _open(tester, api);

    await tester.tap(find.text('Заполнить'));
    await tester.pumpAndSettle();

    verifyNever(() => api.patch(any(), data: any(named: 'data')));
  });

  testWidgets('подставляется только отмеченное, и по нажатию', (tester) async {
    withProducts([_gapped]);
    when(() => api.patch(any(), data: any(named: 'data'))).thenAnswer((_) async => <String, dynamic>{});
    await _open(tester, api);

    await tester.tap(find.text('Заполнить'));
    await tester.pumpAndSettle();
    // Точное совпадение отмечено заранее — кнопка сразу считает одну строку.
    await tester.tap(find.textContaining('Подставить ('));
    await tester.pumpAndSettle();

    verify(() => api.patch('/fridge/products/1810/', data: any(named: 'data'))).called(1);
  });
}
