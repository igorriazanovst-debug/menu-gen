// MG_SWAPFREE: фильтр пищевой группы при замене блюда в меню.
//
// Раньше фильтр был жёстким и невидимым: рецепт другой группы не показывался, а
// бэкенд такую замену отклонял. Пользователь видел рецепт в разделе «Рецепты»,
// но заменить на него блюдо не мог.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/core/constants/food_groups.dart';
import 'package:menugen_app/features/menu/widgets/menu_meal_carousel.dart';

class _MockApi extends Mock implements ApiClient {}

const _recipes = {
  'results': [
    {'id': 42, 'title': 'Сырники солёные с сыром', 'image_url': null},
  ],
};

Future<void> _openPicker(WidgetTester tester, ApiClient api, {String? foodGroup = 'grain'}) async {
  // Виджет берёт цвета из скин-токенов (AppTokens), поэтому нужна настоящая
  // тема приложения, а не голая MaterialApp.
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: Builder(
      builder: (context) => Scaffold(
        body: ElevatedButton(
          onPressed: () => showSwapPicker(
            context,
            apiClient: api,
            menuId: 1,
            itemId: 2,
            currentRecipeId: 7,
            foodGroup: foodGroup,
          ),
          child: const Text('открыть'),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('открыть'));
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() => registerFallbackValue(<String, dynamic>{}));

  group('foodGroupLabel', () {
    test('переводит известные группы', () {
      expect(foodGroupLabel('grain'), 'Зерновые');
      expect(foodGroupLabel('protein'), 'Белки');
    });

    test('незнакомый код не прячется', () => expect(foodGroupLabel('какая-то'), 'какая-то'));

    test('пустое значение даёт пустую строку', () {
      expect(foodGroupLabel(null), '');
      expect(foodGroupLabel('  '), '');
    });
  });

  group('пикер замены', () {
    late _MockApi api;

    setUp(() {
      api = _MockApi();
      when(() => api.get('/recipes/', params: any(named: 'params')))
          .thenAnswer((_) async => Map<String, dynamic>.from(_recipes));
    });

    testWidgets('по умолчанию ищет внутри своей пищевой группы', (tester) async {
      await _openPicker(tester, api);

      final params = verify(() => api.get('/recipes/', params: captureAny(named: 'params'))).captured.last as Map;
      expect(params['food_group'], 'grain');
      expect(find.text('Только группа «Зерновые»'), findsOneWidget);
    });

    testWidgets('снятая галочка убирает фильтр группы из запроса', (tester) async {
      await _openPicker(tester, api);

      await tester.tap(find.byType(Checkbox));
      await tester.pumpAndSettle();

      final params = verify(() => api.get('/recipes/', params: captureAny(named: 'params'))).captured.last as Map;
      expect(params.containsKey('food_group'), isFalse,
          reason: 'без фильтра ищем среди всех рецептов, иначе рецепт «пропадает»');
    });

    testWidgets('у блюда без группы галочки нет', (tester) async {
      await _openPicker(tester, api, foodGroup: null);

      expect(find.byType(Checkbox), findsNothing);
    });

    testWidgets('пустая выдача подсказывает снять фильтр', (tester) async {
      when(() => api.get('/recipes/', params: any(named: 'params')))
          .thenAnswer((_) async => <String, dynamic>{'results': []});

      await _openPicker(tester, api);

      expect(find.textContaining('Снимите галочку'), findsOneWidget);
    });

    testWidgets('замена на другую группу проходит и показывает предупреждение', (tester) async {
      when(() => api.patch('/menu/1/items/2/', data: any(named: 'data')))
          .thenAnswer((_) async => <String, dynamic>{
                'allergen_warning': false,
                'allergens_found': <String>[],
                'calorie_warning': false,
                'recipe_calories': 300,
                'food_group_warning': true,
                'food_group_expected': 'grain',
                'food_group_new': 'protein',
              });

      await _openPicker(tester, api);
      await tester.tap(find.text('Сырники солёные с сыром'));
      await tester.pumpAndSettle();

      verify(() => api.patch('/menu/1/items/2/', data: {'recipe_id': 42})).called(1);
      expect(find.textContaining('другую пищевую группу'), findsOneWidget);
    });

    testWidgets('замена внутри группы обходится без предупреждения', (tester) async {
      when(() => api.patch('/menu/1/items/2/', data: any(named: 'data')))
          .thenAnswer((_) async => <String, dynamic>{'food_group_warning': false});

      await _openPicker(tester, api);
      await tester.tap(find.text('Сырники солёные с сыром'));
      await tester.pumpAndSettle();

      expect(find.textContaining('другую пищевую группу'), findsNothing);
    });
  });
}
