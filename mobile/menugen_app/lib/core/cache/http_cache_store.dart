// Офлайн-кэш GET-ответов API (write-through).
//
// Хранит сырой декодированный JSON последнего успешного ответа по каждому
// (path + отсортированные params) в SharedPreferences. Онлайн-запрос
// перезаписывает запись; при офлайне [CachingApiClient] отдаёт сохранённую
// (любой давности — чтобы разделы работали без сети, с плашкой «не актуально»).
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class CachedEntry {
  final dynamic data;
  final int ts; // millisecondsSinceEpoch последнего успешного ответа
  const CachedEntry(this.data, this.ts);
}

class HttpCacheStore {
  final SharedPreferences prefs;
  HttpCacheStore(this.prefs);

  static const String _prefix = 'mg_httpcache_v1:';

  /// Стабильный ключ по пути и параметрам (порядок params не важен).
  String keyFor(String path, Map<String, dynamic>? params) {
    if (params == null || params.isEmpty) return path;
    final keys = params.keys.toList()..sort();
    final qs = keys.map((k) => '$k=${params[k]}').join('&');
    return '$path?$qs';
  }

  Future<void> save(String key, dynamic data) async {
    try {
      final env = {'ts': DateTime.now().millisecondsSinceEpoch, 'data': data};
      await prefs.setString('$_prefix$key', jsonEncode(env));
    } catch (_) {
      // данные не сериализуются (напр. бинарь) — просто не кэшируем
    }
  }

  CachedEntry? read(String key) {
    final s = prefs.getString('$_prefix$key');
    if (s == null) return null;
    try {
      final env = jsonDecode(s);
      if (env is Map && env['ts'] is int) {
        return CachedEntry(env['data'], env['ts'] as int);
      }
    } catch (_) {}
    return null;
  }
}
