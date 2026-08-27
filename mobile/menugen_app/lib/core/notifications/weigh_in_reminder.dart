// MG_WEIGHREMIND: ежедневное напоминание взвеситься.
//
// Дневник веса бесполезен без регулярности: замер раз в две недели не показывает
// динамику, ради которой его и ведут. Напоминание — местное, оно живёт на
// телефоне и не зависит ни от сервера, ни от интернета.
//
// Про время. Плагин планирует по часовому поясу из пакета timezone, а тот без
// отдельной настройки считает местным UTC. Определять настоящий пояс — это ещё
// один пакет; вместо него мы сами переводим выбранное время из часов телефона в
// UTC и просим плагин повторять ежедневно по совпадению времени. Пока смещение
// телефона не меняется, напоминание приходит в выбранный час; в России перевода
// часов нет, а при переезде в другой пояс достаточно переоткрыть настройку.
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

class WeighInReminder {
  static const _keyEnabled = 'weighin_reminder_enabled';
  static const _keyHour = 'weighin_reminder_hour';
  static const _keyMinute = 'weighin_reminder_minute';

  /// Постоянный id: перепланирование должно заменять напоминание, а не класть
  /// рядом ещё одно. Иначе после пары правок времени телефон звонил бы трижды.
  static const _notificationId = 4201;

  static const _channelId = 'weighin_reminder';
  static const _channelName = 'Напоминание взвеситься';
  static const _channelDescription = 'Ежедневное напоминание записать вес в дневник';

  final FlutterLocalNotificationsPlugin _plugin;
  final SharedPreferences _prefs;

  WeighInReminder({required SharedPreferences prefs, FlutterLocalNotificationsPlugin? plugin})
      : _prefs = prefs,
        _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  bool get enabled => _prefs.getBool(_keyEnabled) ?? false;
  int get hour => _prefs.getInt(_keyHour) ?? 9;
  int get minute => _prefs.getInt(_keyMinute) ?? 0;

  /// Готовит плагин и, если напоминание включено, перепланирует его.
  ///
  /// Перепланирование при запуске нужно из-за перезагрузки телефона: Android
  /// снимает отложенные показы, и без этого напоминание молча пропало бы.
  Future<void> init() async {
    try {
      tzdata.initializeTimeZones();
      await _plugin.initialize(
        const InitializationSettings(
          android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        ),
      );
      if (enabled) await _schedule();
    } catch (e) {
      // Уведомления — приятное дополнение, а не условие работы приложения:
      // на отказ плагина запуск падать не должен.
      debugPrint('WeighInReminder.init: $e');
    }
  }

  /// Включает напоминание на указанное время. Возвращает false, если
  /// пользователь не дал разрешение показывать уведомления.
  Future<bool> enable({required int hour, required int minute}) async {
    final android = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    if (android != null) {
      final granted = await android.requestNotificationsPermission();
      if (granted == false) return false;
    }
    await _prefs.setBool(_keyEnabled, true);
    await _prefs.setInt(_keyHour, hour);
    await _prefs.setInt(_keyMinute, minute);
    await _schedule();
    return true;
  }

  Future<void> disable() async {
    await _prefs.setBool(_keyEnabled, false);
    await _plugin.cancel(_notificationId);
  }

  Future<void> _schedule() async {
    await _plugin.cancel(_notificationId);
    await _plugin.zonedSchedule(
      _notificationId,
      'Пора взвеситься',
      'Запишите вес в дневник — так виден прогресс, а не отдельные цифры.',
      _nextOccurrence(hour, minute),
      const NotificationDetails(
        android: AndroidNotificationDetails(
          _channelId,
          _channelName,
          channelDescription: _channelDescription,
          importance: Importance.defaultImportance,
          priority: Priority.defaultPriority,
        ),
      ),
      // Неточное время намеренно: точные будильники Android с 12-й версии
      // требуют отдельного разрешения, а магазин спрашивает, зачем оно
      // приложению. Напоминанию взвеситься минута туда-сюда безразлична.
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      // Момент показа мы уже посчитали сами и передаём в UTC, поэтому его надо
      // понимать буквально, а не пересчитывать из «времени на стене».
      uiLocalNotificationDateInterpretation: UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time,
    );
  }

  /// Ближайшее наступление указанного времени по часам телефона, в UTC.
  @visibleForTesting
  static tz.TZDateTime nextOccurrence(int hour, int minute, {DateTime? now}) =>
      _nextOccurrence(hour, minute, now: now);

  static tz.TZDateTime _nextOccurrence(int hour, int minute, {DateTime? now}) {
    final current = now ?? DateTime.now();
    var target = DateTime(current.year, current.month, current.day, hour, minute);
    if (!target.isAfter(current)) {
      target = target.add(const Duration(days: 1));
    }
    return tz.TZDateTime.from(target.toUtc(), tz.UTC);
  }
}
