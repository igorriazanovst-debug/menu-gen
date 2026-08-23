// MG_SELFUPDATE: одна проверка обновления после запуска.
//
// Живёт внутри оболочки с вкладками, то есть срабатывает уже после входа:
// показывать предложение обновиться на экране логина незачем, человек пришёл
// не за этим. Виджет ничего не рисует — только ждёт кадр и спрашивает сервер.

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'update_prompt.dart';
import 'update_service.dart';

class SelfUpdateWatcher extends StatefulWidget {
  const SelfUpdateWatcher({super.key});

  @override
  State<SelfUpdateWatcher> createState() => _SelfUpdateWatcherState();
}

class _SelfUpdateWatcherState extends State<SelfUpdateWatcher> {
  // Один раз за запуск: иначе переключение вкладок пересоздавало бы проверку.
  static bool _checkedThisLaunch = false;

  @override
  void initState() {
    super.initState();
    if (_checkedThisLaunch) return;
    _checkedThisLaunch = true;
    WidgetsBinding.instance.addPostFrameCallback((_) => _check());
  }

  Future<void> _check() async {
    final service = context.read<UpdateService?>();
    if (service == null) return; // сборка без апдейтера — сервис не подключён
    try {
      final update = await service.check();
      if (update != null && mounted) {
        await showUpdatePrompt(context, service, update);
      }
    } catch (_) {
      // Обновление — не то, ради чего стоит показывать ошибку при старте.
    }
  }

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}
