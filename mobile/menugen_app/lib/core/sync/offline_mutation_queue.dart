// Персистентная очередь офлайн-мутаций (POST/PUT/PATCH/DELETE).
//
// Мутации попадают сюда ТОЛЬКО когда запрос не дошёл до сервера (офлайн —
// ApiException.isNetwork). Значит сервер их не видел, и повтор при возврате
// сети не задваивает. Очередь переживает перезапуск (SharedPreferences),
// проигрывается по порядку при появлении сети и питает счётчик PendingSync.
//
// В очередь кладём только «пользовательскую активность» (дневник, холодильник,
// избранное) — операции, которым не нужен осмысленный ответ сервера и которые
// безопасно повторить. Генерация меню и пр. в очередь не идут (нужен сервер).
import 'dart:async';
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../connectivity/connectivity_cubit.dart';
import 'pending_sync_cubit.dart';

class OfflineMutationQueue {
  final SharedPreferences prefs;
  final ConnectivityCubit connectivity;
  final PendingSyncCubit pendingSync;

  /// Сырой клиент (без кэш-декоратора) для реплея, чтобы не зациклить очередь.
  ApiClient? _api;

  static const String _key = 'mg_offline_mutations_v1';
  static const String _pendingPart = 'offline_mutations';

  final StreamController<void> _flushed = StreamController<void>.broadcast();
  StreamSubscription<ConnectivityStatus>? _sub;
  Timer? _retry;
  bool _flushing = false;

  /// Сигналит после каждого прогона очереди (UI может перечитать данные).
  Stream<void> get flushed => _flushed.stream;

  OfflineMutationQueue({
    required this.prefs,
    required this.connectivity,
    required this.pendingSync,
  }) {
    _sub = connectivity.stream.listen((s) {
      if (s == ConnectivityStatus.online) flush();
    });
    _updateCounter();
  }

  /// Привязать сырой клиент для реплея (вызывается после конструирования DI).
  void bindApi(ApiClient api) => _api = api;

  /// Можно ли поставить операцию в офлайн-очередь (белый список активности).
  static bool queueable(String path) {
    if (path.startsWith('/diary')) return true;
    if (path.startsWith('/fridge')) return true;
    if (path.contains('/favorite')) return true; // /recipes/<id>/favorite/
    return false;
  }

  List<Map<String, dynamic>> _load() {
    final s = prefs.getString(_key);
    if (s == null) return [];
    try {
      final d = jsonDecode(s);
      if (d is List) {
        return d.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
      }
    } catch (_) {}
    return [];
  }

  Future<void> _store(List<Map<String, dynamic>> q) async {
    try {
      await prefs.setString(_key, jsonEncode(q));
    } catch (_) {}
    _updateCounter(q);
  }

  void _updateCounter([List<Map<String, dynamic>>? q]) =>
      pendingSync.setPart(_pendingPart, (q ?? _load()).length);

  Future<void> enqueue(String method, String path, dynamic data) async {
    final q = _load();
    q.add({
      'method': method,
      'path': path,
      'data': data,
      'ts': DateTime.now().millisecondsSinceEpoch,
    });
    await _store(q);
  }

  int get pendingCount => _load().length;

  Future<void> flush() async {
    if (_flushing || _api == null) return;
    if (connectivity.state == ConnectivityStatus.offline) return;
    var q = _load();
    if (q.isEmpty) {
      _retry?.cancel();
      return;
    }
    _flushing = true;
    try {
      while (q.isNotEmpty) {
        final m = q.first;
        try {
          await _replay(m);
          q.removeAt(0);
          await _store(q);
        } catch (e) {
          if (e is ApiException && e.isNetwork) {
            break; // всё ещё офлайн — сохраняем остаток до следующего раза
          }
          // серверная ошибка (4xx/5xx) — выкидываем, чтобы очередь не застряла
          q.removeAt(0);
          await _store(q);
        }
      }
    } finally {
      _flushing = false;
      _updateCounter(q);
      if (!_flushed.isClosed) _flushed.add(null);
    }
    // Ребро connectivity 'online' может опередить реальную готовность сети —
    // первый flush может упасть; повторяем, пока очередь не опустеет.
    _retry?.cancel();
    if (q.isNotEmpty && connectivity.state != ConnectivityStatus.offline) {
      _retry = Timer(const Duration(seconds: 3), flush);
    }
  }

  Future<void> _replay(Map<String, dynamic> m) async {
    final method = (m['method'] as String? ?? '').toUpperCase();
    final path = m['path'] as String? ?? '';
    final data = m['data'];
    if (path.isEmpty) return;
    switch (method) {
      case 'POST':
        await _api!.post(path, data: data);
        break;
      case 'PUT':
        await _api!.put(path, data: data);
        break;
      case 'PATCH':
        await _api!.patch(path, data: data);
        break;
      case 'DELETE':
        await _api!.delete(path);
        break;
    }
  }

  Future<void> dispose() async {
    _retry?.cancel();
    await _sub?.cancel();
    await _flushed.close();
  }
}
