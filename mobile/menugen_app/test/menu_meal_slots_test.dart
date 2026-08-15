// MG_MEALCOUNT_UI: при трёх приёмах в сетке висели два пустых перекуса.
//
// Число приёмов экран брал из профиля, а выбирают его в шторке генерации —
// у пятиразового профиля меню на три приёма всё равно рисовалось на пять.
// Здесь закреплено, что слоты определяет само меню.
import 'package:flutter_test/flutter_test.dart';
import 'package:menugen_app/features/menu/meal_slots.dart';

Map<String, dynamic> menu({
  String? planType,
  List<Map<String, dynamic>> items = const [],
}) =>
    {
      'id': 1,
      'filters_used': {
        'mode': 'family',
        if (planType != null) 'meal_plan_type': planType,
      },
      'items': items,
    };

Map<String, dynamic> item(String mealType, {String? slot, int day = 0}) => {
      'meal_type': mealType,
      if (slot != null) 'meal_slot': slot,
      'day_offset': day,
    };

void main() {
  group('mealSlotsForMenu', () {
    test('три приёма — перекусов в сетке нет', () {
      expect(mealSlotsForMenu(menu(planType: '3')), mealSlots3);
    });

    test('пять приёмов — оба перекуса на месте', () {
      expect(mealSlotsForMenu(menu(planType: '5')), mealSlots5);
      expect(mealSlotsForMenu(menu(planType: '5')), contains('snack1'));
      expect(mealSlotsForMenu(menu(planType: '5')), contains('snack2'));
    });

    test('меню важнее профиля: перекусов нет — и слотов нет', () {
      // Ровно тот случай из отчёта: профиль пятиразовый, меню сгенерили на три.
      final m = menu(planType: '3', items: [
        item('breakfast'),
        item('lunch'),
        item('dinner'),
      ]);

      expect(mealSlotsForMenu(m), mealSlots3);
    });

    test('старое меню без meal_plan_type: перекусы есть — слоты показываем', () {
      final m = menu(items: [
        item('breakfast'),
        item('snack', slot: 'snack1'),
        item('lunch'),
      ]);

      expect(mealSlotsForMenu(m), mealSlots5);
    });

    test('старое меню без meal_slot опознаётся по meal_type', () {
      final m = menu(items: [item('breakfast'), item('snack')]);

      expect(mealSlotsForMenu(m), mealSlots5);
    });

    test('старое меню без перекусов — три слота', () {
      final m = menu(items: [item('breakfast'), item('lunch'), item('dinner')]);

      expect(mealSlotsForMenu(m), mealSlots3);
    });

    test('перекус в одном дне из семи не прячется', () {
      // Слот смотрим по всему меню: пустой день — не повод убирать строку.
      final m = menu(items: [
        item('breakfast', day: 0),
        item('breakfast', day: 1),
        item('snack', slot: 'snack2', day: 1),
      ]);

      expect(mealSlotsForMenu(m), mealSlots5);
    });

    test('меню ещё не пришло — сетка не падает', () {
      expect(mealSlotsForMenu(null), mealSlots3);
      expect(mealSlotsForMenu(<String, dynamic>{}), mealSlots3);
      expect(mealSlotsForMenu({'filters_used': null, 'items': null}), mealSlots3);
    });
  });

  group('isSnackItem', () {
    test('meal_slot важнее meal_type', () {
      expect(isSnackItem({'meal_type': 'snack', 'meal_slot': 'snack1'}), isTrue);
      expect(isSnackItem({'meal_type': 'snack', 'meal_slot': 'snack2'}), isTrue);
    });

    test('обычный приём перекусом не считается', () {
      expect(isSnackItem({'meal_type': 'lunch', 'meal_slot': 'lunch'}), isFalse);
      expect(isSnackItem({'meal_type': 'breakfast'}), isFalse);
    });
  });
}
