// MG_DAYSUM + MG_WORKOUT: «Итоги дня» и физнагрузки.
//
// До этого дневник показывал, ЧТО съедено, а на вопрос «много это или мало»
// человек отвечал себе сам, в голове. «Итоги» отвечают одним взглядом.
//
// Главное, что проверяется здесь, — чего мы НЕ делаем:
//
// * расход на тренировке НЕ прибавляется к норме и не уменьшает съеденное:
//   норма уже содержит коэффициент активности, и прибавка посчитала бы его
//   дважды — человеку на похудении приложение разрешило бы съесть лишнее;
// * без цели по калориям кольцо не рисуется: процент от выдуманной нормы — это
//   ложь в самом заметном месте экрана;
// * в факт идёт только отмеченное съеденным, плановое ждёт галочки.
//
// Экран проверяется на размере телефона, а не на размере по умолчанию
// (800×600): настоящий телефон уже один раз показал то, чего не видел ни один
// тест.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:menugen_app/core/api/api_client.dart';
import 'package:menugen_app/core/theme/app_theme.dart';
import 'package:menugen_app/features/diary/models/diary_entry.dart';
import 'package:menugen_app/features/diary/models/diary_stats.dart';
import 'package:menugen_app/features/diary/models/workout.dart';
import 'package:menugen_app/features/diary/widgets/day_summary.dart';

class _MockApi extends Mock implements ApiClient {}

// Цвета берём из того же места, что и экран: сверять картинку с выписанными
// в тесте шестнадцатеричными числами значит проверять свою же копию.
final _theme = AppTheme.light();
final Color mealColor = _theme.colorScheme.primary;
// Перебор — отдельный цвет, не accent: accent равен цвету жиров.

DiaryEntry _entry({
  required int id,
  required MealSlot slot,
  required double kcal,
  bool eaten = true,
}) =>
    DiaryEntry(
      id: id,
      date: '2026-11-09',
      mealType: slot.mealType,
      mealSlot: slot,
      recipeId: null,
      recipeTitle: null,
      customName: 'Еда $id',
      nutrition: {'calories': kcal},
      quantity: 1,
      plannedMenuItemId: null,
      isEaten: eaten,
    );

DiaryDayStats _stats({
  double eaten = 1480,
  double planned = 0,
  int burned = 0,
  double proteins = 89,
  double fats = 51,
  double carbs = 167,
}) =>
    DiaryDayStats(
      date: '2026-11-09',
      planned: NutritionBucket(calories: planned, proteins: 0, fats: 0, carbs: 0),
      actual: NutritionBucket(calories: eaten, proteins: proteins, fats: fats, carbs: carbs),
      total: NutritionBucket(calories: eaten, proteins: proteins, fats: fats, carbs: carbs),
      burned: burned,
    );

Future<void> _open(
  WidgetTester tester,
  ApiClient api, {
  DiaryDayStats? stats,
  List<DiaryEntry> entries = const [],
  int? target = 2000,
  int waterMl = 1600,
  VoidCallback? onCalc,
}) async {
  // Размер настоящего телефона: на 800×600 по умолчанию влезает что угодно, и
  // именно поэтому по умолчанию проверять нечего.
  tester.view.physicalSize = const Size(1080, 2256);
  tester.view.devicePixelRatio = 2.75;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: Scaffold(
      body: DaySummaryTab(
        api: api,
        date: '2026-11-09',
        memberId: null,
        stats: stats ?? _stats(),
        entries: entries,
        waterMl: waterMl,
        mealPlanType: '3',
        calorieTarget: target,
        proteinTarget: 110,
        fatTarget: 67,
        carbTarget: 225,
        onCalcTarget: onCalc ?? () {},
      ),
    ),
  ));
  await tester.pumpAndSettle();
}

void main() {
  late _MockApi api;

  setUp(() {
    api = _MockApi();
    when(() => api.get('/diary/weight/', params: any(named: 'params')))
        .thenAnswer((_) async => [
              {'date': '2026-11-09', 'weight_kg': '78.25'},
            ]);
  });

  group('Итоги дня', () {
    testWidgets('кольцо считает съеденное от цели, а не от плана', (tester) async {
      await _open(tester, api, stats: _stats(eaten: 1480, planned: 2400), target: 2000);

      // 1480 из 2000 — это 74 %, независимо от того, что было запланировано.
      expect(find.text('74%'), findsOneWidget);
      expect(find.textContaining('съедено из'), findsOneWidget);
    });

    testWidgets('остаток — это цель минус съеденное', (tester) async {
      await _open(tester, api, stats: _stats(eaten: 1480), target: 2000);

      expect(find.text('осталось'), findsOneWidget);
      // 520 с узким пробелом не разбивается: число трёхзначное.
      expect(find.text('520'), findsOneWidget);
    });

    testWidgets('перебор назван перебором, а не отрицательным остатком', (tester) async {
      await _open(tester, api, stats: _stats(eaten: 2300), target: 2000);

      expect(find.text('перебор'), findsOneWidget);
      expect(find.text('+300'), findsOneWidget);
      expect(find.text('осталось'), findsNothing);
    });

    testWidgets('без цели кольца нет, а есть приглашение её посчитать', (tester) async {
      await _open(tester, api, target: null);

      expect(find.text('от цели'), findsNothing);
      expect(find.textContaining('Цель по калориям не задана'), findsOneWidget);
      expect(find.text('Посчитать'), findsOneWidget);
    });

    testWidgets('без цели съеденное всё равно показано', (tester) async {
      // Это честное число, и от нормы оно не зависит.
      await _open(tester, api, stats: _stats(eaten: 1480), target: null);

      expect(find.text('ккал съедено'), findsOneWidget);
    });

    testWidgets('кнопка «Посчитать» ведёт в калькулятор', (tester) async {
      var tapped = false;
      await _open(tester, api, target: null, onCalc: () => tapped = true);

      await tester.tap(find.text('Посчитать'));

      expect(tapped, isTrue);
    });
  });

  group('Расход на занятиях', () {
    testWidgets('показан отдельной плиткой', (tester) async {
      await _open(tester, api, stats: _stats(eaten: 1480, burned: 550), target: 2000);

      expect(find.text('Потрачено'), findsOneWidget);
      expect(find.text('550 ккал'), findsOneWidget);
    });

    testWidgets('остаток от него не меняется', (tester) async {
      // Ради этого правила всё и устроено именно так: норма уже содержит
      // коэффициент активности. Прибавь расход — и человек на похудении
      // получил бы разрешение съесть лишние полтысячи калорий.
      await _open(tester, api, stats: _stats(eaten: 1480, burned: 550), target: 2000);

      expect(find.text('520'), findsOneWidget); // 2000 − 1480, и никак иначе
      expect(find.text('1 070'), findsNothing); // 520 + 550
    });

    testWidgets('день без занятий цифрой не сорит', (tester) async {
      await _open(tester, api, stats: _stats(burned: 0), target: 2000);

      expect(find.text('Потрачено'), findsOneWidget);
      expect(find.text('0 ккал'), findsNothing);
    });
  });

  group('По приёмам', () {
    testWidgets('в приём идёт только отмеченное съеденным', (tester) async {
      await _open(
        tester,
        api,
        entries: [
          _entry(id: 1, slot: MealSlot.breakfast, kcal: 412),
          _entry(id: 2, slot: MealSlot.lunch, kcal: 735, eaten: false),
        ],
      );

      expect(find.text('412 ккал'), findsOneWidget);
      // Плановый обед без галочки — это ещё не съеденное.
      expect(find.text('735 ккал'), findsNothing);
    });

    testWidgets('пустой приём своей раскладки показан прочерком', (tester) async {
      await _open(tester, api, entries: [_entry(id: 1, slot: MealSlot.breakfast, kcal: 412)]);

      expect(find.text('Обед'), findsOneWidget);
      expect(find.text('Ужин'), findsOneWidget);
      expect(find.text('—'), findsWidgets);
    });

    testWidgets('перекусов при раскладке на три приёма нет', (tester) async {
      await _open(tester, api);

      expect(find.text('Перекус 1'), findsNothing);
    });
  });

  group('Вода и вес', () {
    testWidgets('показываются, но не правятся здесь', (tester) async {
      // Второго места ввода для одного числа нет намеренно: два поля для
      // одного значения расходятся, и человек не знает, какому верить.
      await _open(tester, api, waterMl: 1600);

      expect(find.text('1 600 мл'), findsOneWidget);
      expect(find.text('78.25 кг'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
    });

    testWidgets('без замера веса — прочерк, а не ноль', (tester) async {
      when(() => api.get('/diary/weight/', params: any(named: 'params')))
          .thenAnswer((_) async => const []);

      await _open(tester, api);

      expect(find.text('0 кг'), findsNothing);
    });
  });

  group('Разбор ответа сервера', () {
    test('расход читается из сводки дня', () {
      final s = DiaryDayStats.fromJson({
        'date': '2026-11-09',
        'planned': {'calories': 0, 'proteins': 0, 'fats': 0, 'carbs': 0},
        'actual': {'calories': 1480, 'proteins': 89, 'fats': 51, 'carbs': 167},
        'total': {'calories': 1480, 'proteins': 89, 'fats': 51, 'carbs': 167},
        'burned': 550,
      });

      expect(s.burned, 550);
    });

    test('ответ без расхода — это ноль, а не поломка', () {
      // Так отвечает сервер, который ещё не обновили.
      final s = DiaryDayStats.fromJson({
        'date': '2026-11-09',
        'actual': {'calories': 1480, 'proteins': 0, 'fats': 0, 'carbs': 0},
      });

      expect(s.burned, 0);
    });

    test('занятие без калорий читается пустым, а не нулём', () {
      // Без веса расход не считается, и выдумывать его нельзя. Ноль здесь
      // означал бы «потратил ноль», а это другое утверждение.
      final w = WorkoutLog.fromJson({
        'id': 7,
        'date': '2026-11-09',
        'title': 'Сенокос',
        'duration_min': 90,
        'calories': null,
        'calories_estimated': false,
      });

      expect(w.calories, isNull);
      expect(w.durationLabel, '1 ч 30 мин');
    });

    test('посчитанное нами помечено оценкой', () {
      final w = WorkoutLog.fromJson({
        'id': 8,
        'date': '2026-11-09',
        'title': 'Бег, 10 км/ч',
        'duration_min': 60,
        'calories': 720,
        'calories_estimated': true,
      });

      expect(w.caloriesEstimated, isTrue);
      expect(w.durationLabel, '1 ч');
    });
  });

  group('Чтение КБЖУ записи', () {
    test('число, строка и старая форма читаются одинаково', () {
      double kcal(dynamic raw) => DiaryEntry(
            id: 1,
            date: '2026-11-09',
            mealType: MealType.lunch,
            mealSlot: MealSlot.lunch,
            recipeId: null,
            recipeTitle: null,
            customName: 'x',
            nutrition: {'calories': raw},
            quantity: 1,
            plannedMenuItemId: null,
            isEaten: true,
          ).calories;

      expect(kcal(412), 412);
      expect(kcal('412'), 412);
      expect(kcal('412,5'), 412.5);
      expect(kcal({'value': '412', 'unit': 'ккал'}), 412);
      expect(kcal(null), 0);
    });

    test('количество порций учтено', () {
      final e = DiaryEntry(
        id: 1,
        date: '2026-11-09',
        mealType: MealType.lunch,
        mealSlot: MealSlot.lunch,
        recipeId: null,
        recipeTitle: null,
        customName: 'x',
        nutrition: const {'calories': 200, 'proteins': 10},
        quantity: 2.5,
        plannedMenuItemId: null,
        isEaten: true,
      );

      expect(e.calories, 500);
      expect(e.proteins, 25);
    });
  });

  // ── Полосы ────────────────────────────────────────────────────────────────
  //
  // Проверяется то, что увидел человек на телефоне: полосы были пустыми, хотя
  // числа рядом стояли. Причина — вёрстка: заливка стояла непозиционированным
  // ребёнком Stack, получала свободную высоту и схлопывалась в ноль, а
  // выравнивание у FractionallySizedBox по умолчанию — по центру.
  //
  // Тексты эту поломку не ловят в принципе, поэтому здесь меряется сама
  // заливка. Ищется она по ключу, а не по цвету: цвет углеводов и основной
  // цвет приложения — одно и то же число, и поиск по цвету находил чужую
  // полосу (на этом первая версия проверки и споткнулась).
  group('Полосы', () {
    /// Доля заливки от своего трека и её высота.
    (double, double) bar(WidgetTester tester, String id) {
      final box = find.byKey(Key(id));
      final track = find.ancestor(of: box, matching: find.byType(ClipRRect)).first;
      final size = tester.getSize(box);
      return (size.width / tester.getSize(track).width, size.height);
    }

    Color colorOf(WidgetTester tester, String id) =>
        tester.widget<ColoredBox>(find.byKey(Key(id))).color;

    testWidgets('полоса макроса заполнена по норме, а не пуста', (tester) async {
      // Белки 89 из 110 г — это 81 % полосы.
      await _open(tester, api);

      final (ratio, height) = bar(tester, 'macro-bar-proteins');

      expect(height, greaterThan(0)); // ноль здесь и был той поломкой
      expect(ratio, closeTo(0.81, 0.02));
    });

    testWidgets('заливка растёт слева, а не от середины', (tester) async {
      await _open(tester, api);

      final box = find.byKey(const Key('macro-bar-proteins'));
      final track = find.ancestor(of: box, matching: find.byType(ClipRRect)).first;

      expect(tester.getTopLeft(box).dx, closeTo(tester.getTopLeft(track).dx, 0.5));
    });

    testWidgets('полоса приёма мерится дневной нормой', (tester) async {
      // Обед 488 из нормы 2 000 — это 24 %, а не «весь приём целиком» оттого,
      // что он крупнейший за день.
      await _open(tester, api, entries: [
        _entry(id: 1, slot: MealSlot.breakfast, kcal: 272),
        _entry(id: 2, slot: MealSlot.lunch, kcal: 488),
      ]);

      final (ratio, height) = bar(tester, 'meal-bar-lunch');

      expect(height, greaterThan(0));
      expect(ratio, closeTo(0.244, 0.02));
    });

    testWidgets('без нормы приёмы мерятся самым крупным', (tester) async {
      // Иначе мерить нечем, а полосы от выдуманного числа врут.
      await _open(tester, api, target: null, entries: [
        _entry(id: 1, slot: MealSlot.breakfast, kcal: 272),
        _entry(id: 2, slot: MealSlot.lunch, kcal: 488),
      ]);

      final (ratio, _) = bar(tester, 'meal-bar-lunch');

      expect(ratio, closeTo(1.0, 0.02));
    });

    testWidgets('перебор по макросу отмечен своим цветом', (tester) async {
      // Не accent: accent равен цвету жиров, и перебор по жирам оранжевым по
      // оранжевому был бы невидим.
      await _open(tester, api, stats: _stats(proteins: 130));

      expect(colorOf(tester, 'macro-bar-proteins'), overColor);
    });

    testWidgets('в норме полоса своего цвета', (tester) async {
      await _open(tester, api);

      expect(colorOf(tester, 'macro-bar-proteins'), proteinColor);
      expect(colorOf(tester, 'macro-bar-fats'), fatColor);
      expect(colorOf(tester, 'macro-bar-carbs'), carbColor);
    });

    testWidgets('приём, съевший дневную норму, тоже отмечен', (tester) async {
      await _open(tester, api, entries: [
        _entry(id: 1, slot: MealSlot.lunch, kcal: 2400),
      ]);

      expect(colorOf(tester, 'meal-bar-lunch'), overColor);
      expect(colorOf(tester, 'meal-bar-breakfast'), mealColor);
    });
  });
}
