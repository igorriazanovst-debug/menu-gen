// MG_WEIGHREMIND: настройка ежедневного напоминания взвеситься.
//
// Раньше пункт «Уведомления» в профиле был заглушкой с пустым обработчиком:
// нажать можно, ничего не происходит. Теперь здесь единственное, что приложение
// действительно умеет напоминать, — взвешивание.
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/notifications/weigh_in_reminder.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  WeighInReminder? _reminder;
  bool _enabled = false;
  TimeOfDay _time = const TimeOfDay(hour: 9, minute: 0);
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final reminder = WeighInReminder(prefs: prefs);
    if (!mounted) return;
    setState(() {
      _reminder = reminder;
      _enabled = reminder.enabled;
      _time = TimeOfDay(hour: reminder.hour, minute: reminder.minute);
    });
  }

  Future<void> _toggle(bool value) async {
    final reminder = _reminder;
    if (reminder == null) return;
    setState(() => _busy = true);
    try {
      if (value) {
        final ok = await reminder.enable(hour: _time.hour, minute: _time.minute);
        if (!mounted) return;
        if (!ok) {
          // Разрешение не дали — переключатель обязан вернуться назад, иначе
          // человек будет ждать напоминаний, которых система не покажет.
          setState(() => _enabled = false);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Разрешите уведомления в настройках телефона — без этого напоминание не придёт.'),
            ),
          );
          return;
        }
      } else {
        await reminder.disable();
      }
      if (mounted) setState(() => _enabled = value);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(context: context, initialTime: _time);
    if (picked == null || !mounted) return;
    setState(() => _time = picked);
    if (_enabled) await _toggle(true); // перепланировать на новое время
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Уведомления')),
      body: _reminder == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                SwitchListTile(
                  secondary: const Text('⚖️', style: TextStyle(fontSize: 20)),
                  title: const Text('Напоминать взвеситься'),
                  subtitle: const Text('Каждый день в выбранное время'),
                  value: _enabled,
                  onChanged: _busy ? null : _toggle,
                ),
                ListTile(
                  leading: const Icon(Icons.schedule_outlined),
                  title: const Text('Время напоминания'),
                  trailing: Text(
                    _time.format(context),
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  onTap: _busy ? null : _pickTime,
                ),
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 12, 16, 0),
                  child: Text(
                    'Взвешиваться лучше в одно и то же время — обычно утром, до еды. '
                    'Тогда в дневнике видна динамика, а не разброс от времени суток.',
                    style: TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                ),
              ],
            ),
    );
  }
}
