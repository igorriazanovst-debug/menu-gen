// Раскладка позиций меню по слотам — та же функция, что зовёт MenuScreen.
// Раньше тест держал собственную копию логики и проверял сам себя.
import 'package:flutter_test/flutter_test.dart';
import 'package:menugen_app/features/menu/meal_slots.dart';

void main() {
  group('itemsForSlot', () {
    final items = <Map<String, dynamic>>[
      {'id': 1, 'meal_type': 'breakfast'},
      {'id': 2, 'meal_type': 'snack'},
      {'id': 3, 'meal_type': 'lunch'},
      {'id': 4, 'meal_type': 'snack'},
      {'id': 5, 'meal_type': 'dinner'},
    ];

    test('breakfast direct match', () {
      expect(itemsForSlot(dayItems: items, slot: 'breakfast').length, 1);
    });
    test('snack1 picks first snack', () {
      final r = itemsForSlot(dayItems: items, slot: 'snack1');
      expect(r.length, 1);
      expect(r.first['id'], 2);
    });
    test('snack2 picks second snack', () {
      final r = itemsForSlot(dayItems: items, slot: 'snack2');
      expect(r.length, 1);
      expect(r.first['id'], 4);
    });
    test('snack2 empty when only one snack', () {
      final r = itemsForSlot(dayItems: [
        {'id': 10, 'meal_type': 'snack'},
        {'id': 11, 'meal_type': 'breakfast'},
      ], slot: 'snack2');
      expect(r, isEmpty);
    });
    test('snack1 empty when no snacks', () {
      final r = itemsForSlot(dayItems: [
        {'id': 11, 'meal_type': 'breakfast'},
      ], slot: 'snack1');
      expect(r, isEmpty);
    });
    test('точный meal_slot важнее порядка', () {
      final r = itemsForSlot(dayItems: [
        {'id': 20, 'meal_type': 'snack', 'meal_slot': 'snack2'},
        {'id': 21, 'meal_type': 'snack', 'meal_slot': 'snack1'},
      ], slot: 'snack2');
      expect(r.single['id'], 20);
    });
    test('один рецепт на всю семью — одна карточка', () {
      final r = itemsForSlot(dayItems: [
        {'id': 30, 'meal_type': 'lunch', 'recipe': {'id': 7}, 'member': 1},
        {'id': 31, 'meal_type': 'lunch', 'recipe': {'id': 7}, 'member': 2},
        {'id': 32, 'meal_type': 'lunch', 'recipe': {'id': 8}, 'member': 1},
      ], slot: 'lunch');
      expect(r.map((i) => i['id']), [30, 32]);
    });
  });
}
