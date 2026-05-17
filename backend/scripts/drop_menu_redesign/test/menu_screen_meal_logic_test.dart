// Pure-dart tests for slot mapping used in MenuScreen.
// Не зависит от Flutter (нет imports flutter/*), считается чисто.
import 'package:flutter_test/flutter_test.dart';

List<String> mealSlotsFor(String mealPlanType) =>
    mealPlanType == '5'
        ? const ['breakfast', 'snack1', 'lunch', 'snack2', 'dinner']
        : const ['breakfast', 'lunch', 'dinner'];

List<Map<String, dynamic>> itemsForSlot({
  required List<Map<String, dynamic>> dayItems,
  required String slot,
}) {
  if (slot == 'snack1' || slot == 'snack2') {
    final snacks =
        dayItems.where((i) => (i['meal_type'] as String?) == 'snack').toList();
    if (snacks.isEmpty) return const [];
    if (slot == 'snack1') return [snacks.first];
    if (snacks.length >= 2) return [snacks[1]];
    return const [];
  }
  return dayItems.where((i) => (i['meal_type'] as String?) == slot).toList();
}

void main() {
  group('mealSlotsFor', () {
    test('plan=3', () {
      expect(mealSlotsFor('3'), ['breakfast', 'lunch', 'dinner']);
    });
    test('plan=5', () {
      expect(mealSlotsFor('5'),
          ['breakfast', 'snack1', 'lunch', 'snack2', 'dinner']);
    });
    test('unknown defaults to 3', () {
      expect(mealSlotsFor('zzz'), ['breakfast', 'lunch', 'dinner']);
    });
  });

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
  });
}
