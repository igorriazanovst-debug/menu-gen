import 'package:flutter_bloc/flutter_bloc.dart';

/// MG_T08: global count of locally-queued, not-yet-synced changes.
///
/// Surfaced by [SyncIndicator]. Несколько источников (shopping-очередь тоглов и
/// общая офлайн-очередь мутаций) вносят вклад по ключу — итог суммируется,
/// чтобы источники не перетирали общий счётчик.
class PendingSyncCubit extends Cubit<int> {
  PendingSyncCubit() : super(0);

  final Map<String, int> _parts = {};

  /// Вклад источника [key] в общий счётчик.
  void setPart(String key, int n) {
    _parts[key] = n < 0 ? 0 : n;
    emit(_parts.values.fold(0, (a, b) => a + b));
  }

  /// Совместимость: одиночный источник (shopping-очередь тоглов).
  void set(int n) => setPart('default', n);
}
