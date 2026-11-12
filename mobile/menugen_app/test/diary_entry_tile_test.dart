// MG_NOCUT: строка еды в дневнике не должна резать ни название, ни числа.
//
// Случай с телефона: вместо «куриное филе отварное» было видно «куриное …»,
// а вместо «Б 19 · Ж 2.1 · У 0 г» — «Б 19 · Ж 2.1…». Причина — ListTile:
// он отдаёт названию остаток ширины после чекбокса, калорий и кнопки меню, и
// при крупном системном шрифте остатка не хватает.
//
// Проверяется здесь не картинка, а само переполнение: у абзаца спрашивается
// `didExceedMaxLines`. Экран берётся телефонный (393 точки), и отдельно —
// с увеличенным системным шрифтом: именно он и добил ширину.
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/display/nutrition_detail.dart';
import 'package:menugen_app/core/display/display_prefs_cubit.dart';
import 'package:menugen_app/core/display/food_text_scale.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/diary/models/diary_entry.dart';
import 'package:menugen_app/features/diary/widgets/diary_entry_tile.dart';

class _MockApi extends Mock implements ApiClient {}

DiaryEntry _entry({
  String title = 'куриное филе отварное',
  double kcal = 102,
  double proteins = 19,
  double fats = 2.1,
  double carbs = 0,
  int? grams,
}) =>
    DiaryEntry(
      id: 1,
      date: '2026-11-11',
      mealType: MealType.breakfast,
      mealSlot: MealSlot.breakfast,
      recipeId: null,
      recipeTitle: null,
      customName: title,
      nutrition: {'calories': kcal, 'proteins': proteins, 'fats': fats, 'carbs': carbs},
      quantity: 1,
      grams: grams,
      plannedMenuItemId: null,
      isEaten: true,
    );

/// Переполнен ли абзац с этим текстом (многоточие вместо части строки).
///
/// У названия и у строки БЖУ предела по числу строк нет вовсе, поэтому
/// переполниться они не могут — проверка сторожит, чтобы предел не вернули.
bool _cut(WidgetTester tester, Finder finder) {
  final paragraph = tester.renderObject<RenderParagraph>(finder);
  return paragraph.didExceedMaxLines;
}

Future<void> _show(
  WidgetTester tester,
  DiaryEntry entry, {
  NutritionDetail detail = NutritionDetail.normal,
  FoodTextScale scale = FoodTextScale.normal,
  double textScale = 1.0,
}) async {
  SharedPreferences.setMockInitialValues({
    'nutrition_detail': detail.code,
    'food_text_scale': scale.code,
  });
  final api = _MockApi();
  final cubit = DisplayPrefsCubit(
    prefs: await SharedPreferences.getInstance(),
    apiClient: api,
  );

  // Настоящий телефон: 393 точки шириной. На экране по умолчанию (800) не
  // обрезалось бы ничего, и проверять было бы нечего.
  tester.view.physicalSize = const Size(1080, 2256);
  tester.view.devicePixelRatio = 2.75;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    // Крупный системный шрифт — то, на чём строка и посыпалась. Берём
    // настоящие размеры окна и меняем только масштаб текста: голый
    // MediaQueryData отдал бы поддереву нулевой экран.
    home: Builder(
      builder: (ctx) => MediaQuery(
        // Системный масштаб × наш: настройка размера умножается на системный,
        // и проверять надо именно сочетание — оно и есть худший случай.
        data: MediaQuery.of(ctx)
            .copyWith(textScaler: TextScaler.linear(textScale * scale.factor)),
        child: BlocProvider.value(
          value: cubit,
          child: Scaffold(
            body: ListView(
              children: [
                DiaryEntryTile(
                  entry: entry,
                  accent: const Color(0xFFFB8C00),
                  onToggleEaten: (_) {},
                  onDelete: () {},
                  onEdit: () {},
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  ));
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() => registerFallbackValue(<String, dynamic>{}));

  testWidgets('название видно целиком', (tester) async {
    await _show(tester, _entry());

    final title = find.text('куриное филе отварное', findRichText: true);
    expect(title, findsOneWidget);
    expect(_cut(tester, title), isFalse);
  });

  testWidgets('строка БЖУ видна целиком', (tester) async {
    await _show(tester, _entry());

    expect(find.text('Б 19 · Ж 2.1 · У 0 г'), findsOneWidget);
    expect(_cut(tester, find.text('Б 19 · Ж 2.1 · У 0 г')), isFalse);
  });

  testWidgets('и то и другое при крупном системном шрифте', (tester) async {
    // Ровно тот случай со скриншота: шрифт крупнее обычного.
    await _show(tester, _entry(), textScale: 1.3);

    expect(_cut(tester, find.text('куриное филе отварное', findRichText: true)), isFalse);
    expect(_cut(tester, find.text('Б 19 · Ж 2.1 · У 0 г')), isFalse);
  });

  testWidgets('длинное название переносится, а не обрывается', (tester) async {
    const long = 'сыр сливочный творожный лёгкий с зеленью';
    await _show(tester, _entry(title: long), textScale: 1.3);

    expect(_cut(tester, find.text(long, findRichText: true)), isFalse);
  });

  testWidgets('калорийность рядом с БЖУ, а не вместо названия', (tester) async {
    await _show(tester, _entry());

    expect(find.text('102 ккал'), findsOneWidget);
  });

  testWidgets('в кратком режиме БЖУ нет', (tester) async {
    await _show(tester, _entry(), detail: NutritionDetail.short);

    expect(find.text('Б 19 · Ж 2.1 · У 0 г'), findsNothing);
    expect(find.text('102 ккал'), findsOneWidget);
  });

  testWidgets('в подробном режиме появляется вес порции', (tester) async {
    await _show(tester, _entry(grams: 120), detail: NutritionDetail.detailed, textScale: 1.3);

    final line = find.text('120 г · Б 19 · Ж 2.1 · У 0 г');
    expect(line, findsOneWidget);
    expect(_cut(tester, line), isFalse);
  });

  testWidgets('названия приёма в строке нет', (tester) async {
    // Оно стоит в заголовке раздела прямо над строкой.
    await _show(tester, _entry());

    expect(find.textContaining('Завтрак'), findsNothing);
  });

  testWidgets('наш крупный поверх системного крупного ничего не режет', (tester) async {
    // Худшее сочетание: системный ×1,3 и наш «крупный» (×1,15) — вместе ×1,5.
    await _show(tester, _entry(), scale: FoodTextScale.large, textScale: 1.3);

    expect(_cut(tester, find.text('куриное филе отварное', findRichText: true)), isFalse);
    expect(find.text('Б 19 · Ж 2.1 · У 0 г'), findsOneWidget);
    expect(find.text('102 ккал'), findsOneWidget);
  });

  testWidgets('длинное название при худшем сочетании тоже целиком', (tester) async {
    const long = 'сыр сливочный творожный лёгкий с зеленью';
    await _show(tester, _entry(title: long), scale: FoodTextScale.large, textScale: 1.3);

    expect(_cut(tester, find.text(long, findRichText: true)), isFalse);
  });
}
