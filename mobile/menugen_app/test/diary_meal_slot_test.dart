// MG_MEALSLOT: точное место приёма в дне.
//
// Раньше запись знала только род еды, и оба перекуса слипались в один раздел.
// Теперь у неё есть слот: завтрак, перекус 1, обед, перекус 2, ужин.
//
// Проверяется то, на чём такие вещи обычно и ломаются: разбор ответа сервера
// (включая ответ старого формата из офлайн-кэша) и согласие слота с родом еды.
import 'package:flutter_test/flutter_test.dart';
import 'package:menugen_app/features/diary/models/diary_entry.dart';

Map<String, dynamic> _json({String? slot, String mealType = 'snack'}) => {
      'id': 1,
      'date': '2026-09-08',
      'meal_type': mealType,
      if (slot != null) 'meal_slot': slot,
      'custom_name': 'Проверочное',
      'nutrition': <String, dynamic>{},
      'quantity': 1,
      'is_eaten': false,
    };

void main() {
  group('MG_MEALSLOT: разбор ответа сервера', () {
    test('слот берётся из ответа', () {
      final entry = DiaryEntry.fromJson(_json(slot: 'snack2'));
      expect(entry.mealSlot, MealSlot.snack2);
      expect(entry.mealType, MealType.snack);
    });

    test('без слота — выводится из рода еды', () {
      // Так выглядит ответ из офлайн-кэша, снятый до обновления приложения.
      final entry = DiaryEntry.fromJson(_json());
      expect(entry.mealSlot, MealSlot.snack1);
    });

    test('незнакомый слот не роняет разбор', () {
      final entry = DiaryEntry.fromJson(_json(slot: 'supper', mealType: 'dinner'));
      expect(entry.mealSlot, MealSlot.dinner);
    });
  });

  group('MG_MEALSLOT: слот и род еды не расходятся', () {
    test('у каждого слота есть род еды', () {
      for (final slot in MealSlot.values) {
        expect(slot.mealType, isNotNull, reason: slot.value);
      }
      expect(MealSlot.snack1.mealType, MealType.snack);
      expect(MealSlot.snack2.mealType, MealType.snack);
    });

    test('у каждого рода еды есть слот по умолчанию', () {
      for (final type in MealType.values) {
        expect(MealSlot.fromMealType(type).mealType, type, reason: type.value);
      }
    });
  });

  group('MG_MEALSLOT: раскладка дня', () {
    test('три приёма — без перекусов', () {
      expect(MealSlot.forPlan('3'),
          [MealSlot.breakfast, MealSlot.lunch, MealSlot.dinner]);
    });

    test('пять приёмов — с двумя перекусами, по ходу дня', () {
      expect(MealSlot.forPlan('5'), [
        MealSlot.breakfast,
        MealSlot.snack1,
        MealSlot.lunch,
        MealSlot.snack2,
        MealSlot.dinner,
      ]);
    });

    test('неизвестная раскладка не ломает экран', () {
      expect(MealSlot.forPlan(null),
          [MealSlot.breakfast, MealSlot.lunch, MealSlot.dinner]);
    });
  });
}
