// MG_WEIGHREMIND: когда именно сработает ежедневное напоминание.
//
// Показ планируется в UTC, а время пользователь выбирает по часам телефона.
// Ошибка тут не видна ни на экране, ни в логах: напоминание просто приходит не
// в тот час — или, если выбранное время уже прошло, приходит сегодня же задним
// числом. Поэтому пересчёт проверяется отдельно от плагина.
//
// Сравниваем моменты через isAtSameMomentAs, а не через ==: оператор равенства
// у DateTime учитывает ещё и признак «это UTC», поэтому 09:00Z и местные 09:00
// он считает разными значениями, даже когда машина живёт по UTC.
import 'package:flutter_test/flutter_test.dart';
import 'package:menugen_app/core/notifications/weigh_in_reminder.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;

void main() {
  setUpAll(tzdata.initializeTimeZones);

  void ожидаемМомент(DateTime получено, DateTime ожидание) {
    expect(
      получено.isAtSameMomentAs(ожидание),
      isTrue,
      reason: 'ожидали $ожидание, получили $получено',
    );
  }

  group('ближайшее наступление времени', () {
    test('сегодня, если время ещё не прошло', () {
      final now = DateTime(2026, 8, 27, 7, 30);

      final next = WeighInReminder.nextOccurrence(9, 0, now: now);

      ожидаемМомент(next, DateTime(2026, 8, 27, 9, 0));
    });

    test('завтра, если время уже прошло', () {
      final now = DateTime(2026, 8, 27, 21, 15);

      final next = WeighInReminder.nextOccurrence(9, 0, now: now);

      ожидаемМомент(next, DateTime(2026, 8, 28, 9, 0));
    });

    test('минута в минуту считается прошедшей', () {
      // Иначе включение ровно в 9:00 поставило бы показ на «сейчас», и
      // уведомление прилетело бы мгновенно — как ошибка, а не напоминание.
      final now = DateTime(2026, 8, 27, 9, 0);

      final next = WeighInReminder.nextOccurrence(9, 0, now: now);

      ожидаемМомент(next, DateTime(2026, 8, 28, 9, 0));
    });

    test('переход через полночь считается верно', () {
      final now = DateTime(2026, 8, 27, 23, 50);

      final next = WeighInReminder.nextOccurrence(0, 30, now: now);

      ожидаемМомент(next, DateTime(2026, 8, 28, 0, 30));
    });

    test('планируется в UTC', () {
      // Плагину нужен момент времени в поясе, а местным поясом пакета timezone
      // без отдельной настройки считается UTC — от него и отталкиваемся.
      final next = WeighInReminder.nextOccurrence(9, 0, now: DateTime(2026, 8, 27, 7, 0));

      expect(next.location.name, 'UTC');
      expect(next.isUtc, isTrue);
    });
  });
}
